#!/usr/bin/env bash
# The work loop. Runs headless under cron. Flow (in spec order):
# kill switch -> lock -> circuit breaker -> budget -> timers -> gather inputs
# -> triage (cheap) -> conductor (Fable, xhigh) -> route -> worker (cheap)
# -> secrets scan (veto) -> diff hygiene -> verifier (Fable, high) -> final vote
# -> log -> STATE update.
#
# Security invariants (see build spec S1-S4):
#   S1: untrusted text (issues, commits, CI output, diffs) is only ever moved
#       through FILES and redirections — never interpolated into a command.
#   S2: prompts wrap untrusted input in <untrusted-input> tags.
#   S3: the worker acts only in its per-run worktree; verify.sh independently
#       asserts nothing outside it changed.
#   S4: scan-secrets.sh has veto power over every other signal.
#
# Fallback is DISABLED on conductor and verifier calls: the claude CLI only
# reroutes when --fallback-model is passed, and we never pass it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---- config (override via environment) ----
DAILY_CAP="${LOOP_DAILY_CAP:-5.00}"          # dollars
MONTHLY_CAP="${LOOP_MONTHLY_CAP:-50.00}"     # dollars
RUN_CEILING_SECS="${LOOP_RUN_CEILING:-2700}" # 45 min overall wall clock
CONDUCTOR_TIMEOUT=900                        # 15 min
WORKER_TIMEOUT=1200                          # 20 min
VERIFIER_TIMEOUT=600                         # 10 min
TRIAGE_TIMEOUT=300
CHEAP_MODEL="${LOOP_CHEAP_MODEL:-anthropic/claude-haiku-4-5-20251001}"
FABLE_MODEL="claude-fable-5"
MAX_TOKENS=64000                             # tune from observed data post-shakedown
DIFF_CHAR_CAP=200000                         # ~50k tokens; bigger is failed-oversize
LOCKFILE_EXCLUDES=(':(exclude)package-lock.json' ':(exclude)yarn.lock' ':(exclude)pnpm-lock.yaml' ':(exclude)dashboard/package-lock.json')

RUN_ID="$(date +%Y%m%d-%H%M%S)-$$"
LOGDIR="$ROOT/loop/logs"
LOG="$LOGDIR/run-$RUN_ID.log"
LOCK="$ROOT/loop/memory/run.lock"
PAUSED="$ROOT/loop/PAUSED"
STATE="$ROOT/loop/memory/STATE.md"
BLOCKED="$ROOT/loop/blocked-items.txt"
TRUST="$ROOT/loop/scripts/trust-log.sh"
COST="$ROOT/loop/scripts/cost-log.sh"
TMP="$(mktemp -d)"
WT=""
START_EPOCH="$(date +%s)"

mkdir -p "$LOGDIR"
log()   { printf '%s\n' "$*" >> "$LOG"; }
alert() { echo "ALERT [$RUN_ID]: $*" >&2; log "alert=$*"; }
pause_system() { printf '%s: %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" > "$PAUSED"; alert "⛔ PAUSED created: $*"; }
die()   { log "outcome=$1"; shift; [ $# -gt 0 ] && alert "$*"; exit 1; }

state_note() { # append up to 3 lines under ## recent, cap file at 100 lines
  printf '%s\n' "$@" | head -3 | sed "s/^/- $(date '+%m-%d %H:%M') /" >> "$STATE"
  tail -100 "$STATE" > "$TMP/state" && cp "$TMP/state" "$STATE"
}

run_with_timeout() { # seconds cmd... (redirections on the call are inherited)
  local secs="$1"; shift
  # <&0 re-attaches the caller's stdin: background jobs otherwise get /dev/null
  "$@" <&0 & local pid=$!
  ( sleep "$secs" && kill -TERM "$pid" 2>/dev/null ) & local dog=$!
  local rc=0; wait "$pid" || rc=$?
  kill "$dog" 2>/dev/null; wait "$dog" 2>/dev/null || true
  return "$rc"
}

check_deadline() {
  if [ $(( $(date +%s) - START_EPOCH )) -gt "$RUN_CEILING_SECS" ]; then
    log "anomaly=run-ceiling-exceeded"
    die "failure-timeout" "run exceeded ${RUN_CEILING_SECS}s wall-clock ceiling"
  fi
}

# ---- 1. kill switch: zero API calls past this point if PAUSED ----
if [ -f "$PAUSED" ]; then
  log "run_id=$RUN_ID"; log "outcome=paused-noop"
  exit 0
fi

log "run_id=$RUN_ID"
log "ts=$(date '+%Y-%m-%dT%H:%M:%S')"

# ---- 2. lock ----
if [ -f "$LOCK" ]; then
  lock_age=$(( $(date +%s) - $(stat -f %m "$LOCK") ))
  if [ "$lock_age" -lt 7200 ]; then
    log "outcome=lock-held"
    exit 0
  fi
  alert "stale run.lock (${lock_age}s old) — crashed run; cleaning up"
  old_wt="$(grep -m1 '^worktree=' "$LOCK" | cut -d= -f2- || true)"
  if [ -n "$old_wt" ] && [ -d "$old_wt" ]; then
    git -C "$ROOT" worktree remove --force "$old_wt" 2>/dev/null || rm -rf "$old_wt"
  fi
  rm -f "$LOCK"
fi
cleanup() {
  rm -f "$LOCK"
  if [ -n "$WT" ]; then git -C "$ROOT" worktree remove --force "$WT" 2>/dev/null || true; fi
  rm -rf "$TMP"
}
trap cleanup EXIT INT TERM
printf 'run_id=%s\nworktree=\n' "$RUN_ID" > "$LOCK"

# ---- 3. circuit breaker: 3 consecutive failed runs -> PAUSED ----
last3="$(ls -1 "$LOGDIR"/run-*.log 2>/dev/null | grep -v "run-$RUN_ID" | sort | tail -3 || true)"
if [ "$(printf '%s\n' "$last3" | grep -c . || true)" -eq 3 ]; then
  fails=0
  while IFS= read -r f; do
    grep -q '^outcome=failure' "$f" && fails=$((fails + 1))
  done <<< "$last3"
  if [ "$fails" -eq 3 ]; then
    pause_system "circuit breaker: three consecutive runs ended in failure"
    die "paused-circuit-breaker"
  fi
fi

# ---- 4. budget ----
today="$("$COST" --today)"; month="$("$COST" --month)"
if awk -v a="$today" -v cap="$DAILY_CAP" 'BEGIN { exit !(a >= cap) }'; then
  die "budget-daily" "daily budget breached: \$$today >= \$$DAILY_CAP"
fi
if awk -v a="$month" -v cap="$MONTHLY_CAP" 'BEGIN { exit !(a >= cap) }'; then
  die "budget-monthly" "monthly budget breached: \$$month >= \$$MONTHLY_CAP"
fi

# ---- API keys: sourced at runtime from .env; never read by a human or logged ----
if [ -f "$ROOT/.env" ]; then set -a; . "$ROOT/.env"; set +a; fi

# ---- cost helpers ----
log_llm_cost() { # after an llm call: read usage from llm's own log db
  local u in_tok out_tok
  u="$(llm logs list -n 1 --json 2>/dev/null || true)"
  in_tok="$(printf '%s' "$u" | jq -r '.[0].input_tokens // empty' 2>/dev/null || true)"
  out_tok="$(printf '%s' "$u" | jq -r '.[0].output_tokens // empty' 2>/dev/null || true)"
  [ -z "$in_tok" ] && log "anomaly=missing-usage-cheap-model"
  "$COST" --log "$CHEAP_MODEL" "${in_tok:-}" "${out_tok:-}"
  log "cheap_tokens_in=${in_tok:--} cheap_tokens_out=${out_tok:--}"
}

log_fable_cost() { # $1 = claude -p json envelope file
  local in_tok out_tok dollars
  in_tok="$(jq -r '.usage.input_tokens // empty' "$1" 2>/dev/null || true)"
  out_tok="$(jq -r '.usage.output_tokens // empty' "$1" 2>/dev/null || true)"
  dollars="$(jq -r '.total_cost_usd // empty' "$1" 2>/dev/null || true)"
  [ -z "$in_tok" ] && log "anomaly=missing-usage-fable"
  "$COST" --log "$FABLE_MODEL" "${in_tok:-}" "${out_tok:-}" ${dollars:+"$dollars"}
  log "fable_tokens_in=${in_tok:--} fable_tokens_out=${out_tok:--} fable_cost=${dollars:--}"
}

# ---- step-9 validation for every Fable response ----
validate_fable() { # envelope-file stage -> echoes inner result text on success
  local f="$1" stage="$2"
  cp "$f" "$LOGDIR/raw-$RUN_ID-$stage.json" 2>/dev/null || true
  if ! jq -e . "$f" > /dev/null 2>&1; then
    log "anomaly=truncated-or-unparseable-json-$stage"
    die "failure-$stage" "$stage returned unparseable JSON; raw kept at raw-$RUN_ID-$stage.json"
  fi
  if grep -q '"stop_reason"[[:space:]]*:[[:space:]]*"refusal"' "$f"; then
    log "anomaly=refusal-$stage"
    die "failure-$stage" "$stage response was a REFUSAL — not silently swallowed; see raw-$RUN_ID-$stage.json"
  fi
  if [ "$(jq -r '.is_error // false' "$f")" != "false" ] || [ "$(jq -r '.subtype // empty' "$f")" != "success" ]; then
    log "anomaly=error-envelope-$stage"
    die "failure-$stage" "$stage returned an error envelope; see raw-$RUN_ID-$stage.json"
  fi
  # Reroute check: the requested model must have actually served the call.
  # (modelUsage also lists the CLI's small internal helper calls — those are
  # normal; a silent reroute shows as $FABLE_MODEL being ABSENT.)
  if ! jq -e --arg m "$FABLE_MODEL" '(.modelUsage // {}) | keys[] | select(startswith($m))' "$f" > /dev/null 2>&1; then
    log "anomaly=reroute-$stage"
    die "failure-$stage" "$stage was not served by $FABLE_MODEL — trust ledger integrity requires it; see raw-$RUN_ID-$stage.json"
  fi
  jq -r '.result // empty' "$f"
}

extract_json_block() { # stdin: text possibly fenced -> first {...} block
  sed -n '/^```/!p' | awk '/{/ { seen = 1 } seen { print }'
}

count_prior_fails() { # item-string -> how many past runs failed on it
  local n=0 f
  for f in "$LOGDIR"/run-*.log; do
    [ -f "$f" ] || continue
    [ "$f" = "$LOG" ] && continue
    if grep -qxF "item=$1" "$f" 2>/dev/null && grep -q '^outcome=failure' "$f"; then n=$((n + 1)); fi
  done
  echo "$n"
}

ensure_label() { gh label create "$1" --color 5319e7 2>/dev/null || true; }

open_queue_pr() { # skill work-order-file reason  (queue WITHOUT running the worker)
  local skill="$1" order="$2" reason="$3" branch qwt
  branch="agentic/queue-$RUN_ID"
  qwt="$TMP/queue-wt"
  git -C "$ROOT" worktree add -b "$branch" "$qwt" HEAD > /dev/null 2>&1
  mkdir -p "$qwt/loop/queue"
  {
    echo "# Queued work order — $RUN_ID"
    echo "Reason queued: $reason"
    echo '```json'; cat "$order"; echo '```'
  } > "$qwt/loop/queue/$RUN_ID.md"
  git -C "$qwt" add loop/queue && git -C "$qwt" commit -q -m "agentic queue: $skill ($RUN_ID)"
  ensure_label "agentic:$skill"
  if git -C "$qwt" push -q -u origin "$branch" && \
     gh pr create --draft --head "$branch" --label "agentic:$skill" \
       --title "agentic queue: $skill ($RUN_ID)" \
       --body-file "$qwt/loop/queue/$RUN_ID.md" >> "$LOG" 2>&1; then
    log "queued_pr=yes"
  else
    log "anomaly=queue-pr-failed"
    alert "could not open queue draft PR for $skill"
  fi
  git -C "$ROOT" worktree remove --force "$qwt" 2>/dev/null || true
}

# ---- 6. gather inputs safely: files only, no interpolation ----
git -C "$ROOT" log --oneline -20 > "$TMP/commits.txt"
gh issue list --limit 20 --json number,title,body,author \
  --jq '.[] | "issue #\(.number) by @\(.author.login)\ntitle: \(.title)\nbody: \(.body)\n---"' \
  > "$TMP/issues.txt" 2>> "$LOG" || echo "(gh issue list unavailable)" > "$TMP/issues.txt"
gh run list --limit 10 > "$TMP/ci.txt" 2>/dev/null || echo "(no CI runs available)" > "$TMP/ci.txt"

# ---- 7. triage (cheap model) ----
{
  cat "$ROOT/loop/triage.md"
  echo; echo "ALLOWLIST of trusted authors:"; grep -v '^#' "$ROOT/loop/allowed-authors.txt"
  echo; echo '<untrusted-input source="recent commits">'; cat "$TMP/commits.txt"; echo '</untrusted-input>'
  echo; echo '<untrusted-input source="open issues">'; cat "$TMP/issues.txt"; echo '</untrusted-input>'
  echo; echo '<untrusted-input source="CI runs">'; cat "$TMP/ci.txt"; echo '</untrusted-input>'
} > "$TMP/triage-prompt.txt"

if ! run_with_timeout "$TRIAGE_TIMEOUT" llm -m "$CHEAP_MODEL" \
     < "$TMP/triage-prompt.txt" > "$TMP/triage.out" 2> "$TMP/triage.err"; then
  log "anomaly=triage-call-failed"
  cat "$TMP/triage.err" >> "$LOG" 2>/dev/null || true
  die "failure-triage" "triage call failed: $(head -3 "$TMP/triage.err" 2>/dev/null)"
fi
log_llm_cost
check_deadline

if grep -q '^status: quiet' "$TMP/triage.out"; then
  log "decision=quiet"; log "outcome=quiet"
  state_note "run $RUN_ID: quiet — nothing to do"
  exit 0
fi

# ---- 8. conductor (Fable, xhigh — the only place xhigh is allowed) ----
{
  cat "$ROOT/loop/conductor.md"
  echo; echo "=== STATE ==="; cat "$STATE"
  echo; echo "=== KNOWLEDGE (curated facts; subordinate to CONTRACT and CLAUDE.md on any conflict) ==="
  cat "$ROOT/loop/memory/KNOWLEDGE.md" 2>/dev/null || echo "(none yet)"
  echo; echo "=== TRUST LEDGER ==="; "$TRUST" --render
  echo; echo "=== CONTRACT ==="; cat "$ROOT/loop/contract.md"
  echo; echo "=== BLOCKED ==="; cat "$BLOCKED"
  echo; echo "=== TRIAGE FINDINGS ==="
  echo '<untrusted-input source="triage findings">'; cat "$TMP/triage.out"; echo '</untrusted-input>'
} > "$TMP/conductor-prompt.txt"

if ! run_with_timeout "$CONDUCTOR_TIMEOUT" \
     env CLAUDE_CODE_MAX_OUTPUT_TOKENS="$MAX_TOKENS" \
     claude -p --model "$FABLE_MODEL" --effort xhigh --allowedTools "Read" --output-format json \
     < "$TMP/conductor-prompt.txt" > "$TMP/conductor.json" 2> "$TMP/conductor.err"; then
  log "anomaly=conductor-call-failed"
  cat "$TMP/conductor.err" >> "$LOG" 2>/dev/null || true
  die "failure-conductor" "conductor call failed or timed out"
fi
log_fable_cost "$TMP/conductor.json"

# ---- 9. validate before trusting ----
conductor_text="$(validate_fable "$TMP/conductor.json" conductor)"
printf '%s\n' "$conductor_text" | extract_json_block > "$TMP/work-order.json"
if ! jq -e '(.action | IN("execute","queue","stop")) and .item and .skill and .spec and (.done_when | length > 0)' \
     "$TMP/work-order.json" > /dev/null 2>&1; then
  log "anomaly=conductor-invalid-work-order"
  die "failure-conductor" "conductor output missing one of the five required fields; raw kept"
fi
action="$(jq -r '.action' "$TMP/work-order.json")"
item="$(jq -r '.item' "$TMP/work-order.json")"
skill="$(jq -r '.skill' "$TMP/work-order.json")"
log "decision=$action"; log "skill=$skill"; log "item=$item"
log "spec=$(jq -r '.spec' "$TMP/work-order.json" | head -1)"
check_deadline

# ---- 10. route ----
if [ "$action" = "stop" ]; then
  log "outcome=stopped"
  state_note "run $RUN_ID: conductor stopped — nothing worth doing"
  exit 0
fi
if grep -vE '^\s*(#|$)' "$BLOCKED" | grep -qxF "$item"; then
  log "anomaly=conductor-picked-blocked-item"
  alert "conductor tried blocked item: $item — forced to queue"
  open_queue_pr "$skill" "$TMP/work-order.json" "item is on blocked-items.txt (conductor tried it anyway)"
  log "outcome=queued-blocked"
  exit 0
fi
if [ "$action" = "queue" ]; then
  open_queue_pr "$skill" "$TMP/work-order.json" "conductor decision: queue"
  log "outcome=queued"
  state_note "run $RUN_ID: queued $skill — $item"
  exit 0
fi
# action=execute: the script re-checks the tier; the model's opinion is not authoritative.
tier="$("$TRUST" --tier "$skill")"
ship_allowed=no
if [ "$tier" = "auto" ]; then ship_allowed=yes; else log "tier_gate=$tier (execute allowed, ship forced to queue)"; fi

# ---- 11. worker (cheap model, per-run worktree) ----
WT="$TMP/wt-$RUN_ID"
git -C "$ROOT" worktree add -b "agentic/work-$RUN_ID" "$WT" HEAD > /dev/null 2>&1
printf 'run_id=%s\nworktree=%s\n' "$RUN_ID" "$WT" > "$LOCK"

{
  cat "$ROOT/loop/workers/implement.md"
  echo
  echo "WORK ORDER (JSON):"
  cat "$TMP/work-order.json"
  echo
  echo "HARNESS OUTPUT CONTRACT: you are a text model; your edits are applied by the"
  echo "harness. Output ONLY a unified diff (git apply format, paths relative to the"
  echo "repo root) implementing the ONE next step. Include the IMPLEMENTATION.md file"
  echo "as a new file in the diff. No prose outside the diff. If you must stop for a"
  echo "missing credential or undocumented decision, the diff contains ONLY"
  echo "IMPLEMENTATION.md with your question."
} > "$TMP/worker-prompt.txt"

if ! run_with_timeout "$WORKER_TIMEOUT" llm -m "$CHEAP_MODEL" \
     < "$TMP/worker-prompt.txt" > "$TMP/worker.out" 2> "$TMP/worker.err"; then
  log "anomaly=worker-call-failed"
  "$TRUST" --log "$skill" fail
  die "failure-worker" "worker call failed or timed out"
fi
log_llm_cost
check_deadline

sed -n '/^```/!p' "$TMP/worker.out" > "$TMP/worker.patch"
if ! git -C "$WT" apply --whitespace=nowarn "$TMP/worker.patch" 2>> "$LOG"; then
  log "anomaly=worker-patch-unappliable"
  "$TRUST" --log "$skill" fail
  if [ "$(count_prior_fails "$item")" -ge 1 ]; then
    printf '%s\n' "$item" >> "$BLOCKED"
    alert "second failure on '$item' — added to blocked-items.txt"
  fi
  die "failure-worker" "worker patch did not apply"
fi
git -C "$WT" add -A

# ---- 12. secrets scan BEFORE verification — veto power, ⛔ on hit ----
if ! "$ROOT/loop/guardrails/scan-secrets.sh" "$WT" >> "$LOG" 2>&1; then
  pause_system "secrets scan flagged the worker diff on run $RUN_ID"
  "$TRUST" --log "$skill" fail
  die "failure-secrets" "secrets scan HIT — worktree discarded, system paused"
fi

# ---- 13. diff hygiene for the verifier ----
git -C "$WT" diff HEAD -- . "${LOCKFILE_EXCLUDES[@]}" > "$TMP/clean.diff"
diff_chars="$(wc -c < "$TMP/clean.diff" | tr -d ' ')"
if [ "$diff_chars" -gt "$DIFF_CHAR_CAP" ]; then
  log "anomaly=oversize-diff-$diff_chars-chars"
  "$TRUST" --log "$skill" fail
  printf '%s\n' "$item" >> "$BLOCKED"
  alert "diff too big to review ($diff_chars chars) — failed-oversize, item blocked"
  die "failure-oversize" "a diff too big to review is a fail by definition"
fi

# ---- 14. verifier (fresh Fable, effort high, no tools) ----
{
  cat "$ROOT/loop/workers/verify.md"
  echo; echo "SPEC:"; cat "$TMP/work-order.json"
  echo; echo '<untrusted-input source="diff under review">'; cat "$TMP/clean.diff"; echo '</untrusted-input>'
} > "$TMP/verifier-prompt.txt"

if ! run_with_timeout "$VERIFIER_TIMEOUT" \
     env CLAUDE_CODE_MAX_OUTPUT_TOKENS="$MAX_TOKENS" \
     claude -p --model "$FABLE_MODEL" --effort high --allowedTools "" --output-format json \
     < "$TMP/verifier-prompt.txt" > "$TMP/verifier.json" 2> "$TMP/verifier.err"; then
  log "anomaly=verifier-call-failed"
  "$TRUST" --log "$skill" fail
  die "failure-verifier" "verifier call failed or timed out"
fi
log_fable_cost "$TMP/verifier.json"
verifier_text="$(validate_fable "$TMP/verifier.json" verifier)"
verdict="$(printf '%s\n' "$verifier_text" | grep -m1 -E '^(PASS|FAIL):' || true)"
log "verifier=$verdict"

# ---- 15. final vote: secrets clean AND Fable PASS AND verify.sh AND auto tier ----
script_vote=fail
if "$ROOT/loop/guardrails/verify.sh" "$WT" >> "$LOG" 2>&1; then script_vote=pass; fi
log "verify_sh=$script_vote"

case "$verdict" in PASS:*) fable_vote=pass ;; *) fable_vote=fail ;; esac

if [ "$fable_vote" = "pass" ] && [ "$script_vote" = "pass" ]; then
  "$TRUST" --log "$skill" pass
  git -C "$WT" commit -q -m "agentic $skill: $item ($RUN_ID)"
  ensure_label "agentic:$skill"
  if [ "$ship_allowed" = "yes" ]; then
    if git -C "$WT" push -q -u origin "agentic/work-$RUN_ID" && \
       gh pr create --head "agentic/work-$RUN_ID" --label "agentic:$skill" \
         --title "agentic ship: $skill ($RUN_ID)" --body-file "$TMP/work-order.json" >> "$LOG" 2>&1; then
      log "outcome=shipped-ready-pr"
      state_note "run $RUN_ID: SHIPPED (ready PR) $skill — $item"
    else
      log "anomaly=ship-pr-failed"
      die "failure-ship" "verified work could not be pushed as ready PR"
    fi
  else
    if git -C "$WT" push -q -u origin "agentic/work-$RUN_ID" && \
       gh pr create --draft --head "agentic/work-$RUN_ID" --label "agentic:$skill" \
         --title "agentic draft: $skill ($RUN_ID)" --body-file "$TMP/work-order.json" >> "$LOG" 2>&1; then
      log "outcome=queued-draft-pr"
      state_note "run $RUN_ID: draft PR for $skill (tier $tier) — $item"
    else
      log "anomaly=draft-pr-failed"
      die "failure-draft-pr" "verified work could not be pushed as draft PR"
    fi
  fi
else
  "$TRUST" --log "$skill" fail
  if [ "$(count_prior_fails "$item")" -ge 1 ]; then
    printf '%s\n' "$item" >> "$BLOCKED"
    alert "second failure on '$item' — added to blocked-items.txt; verify fails twice wakes the human"
  fi
  state_note "run $RUN_ID: FAILED $skill (fable=$fable_vote script=$script_vote) — $item"
  die "failure-verify" "final vote failed: fable=$fable_vote verify.sh=$script_vote"
fi
