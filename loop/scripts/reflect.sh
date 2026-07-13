#!/usr/bin/env bash
# The reflector's ENFORCEMENT layer. The model proposes; this script decides
# what is even mechanically possible:
#   Tier 1 (auto-apply)  : append-only facts, ONLY to loop/memory/KNOWLEDGE.md
#   Tier 2 (draft PR)    : ONLY loop/triage.md, loop/conductor.md,
#                          loop/workers/*, loop/skills/*
#   Tier 3 (never)       : protected files — proposals become digest notes only
# The allowlist is HARDCODED HERE, not asked of the model. The model's tier
# claim is checked, never trusted: a tier-1 claim on a tier-2 path is downgraded
# to the PR path; a claim on anything else is a logged containment event.
# Oversize tier-2 patches (>1 file or >40 lines) are rejected before a PR is
# opened — brains change in small diffs or not at all.
#
# --test-input <file.json>  bypass the API and treat the file as the model
#                            response (chaos-testing the enforcement, not the
#                            model's manners)
# --rollback <record-file>   revert a tier-1 application recorded in
#                            loop/memory/reflections/
#
# A broken reflector must never stop the work loop: 3 consecutive failed nights
# alert loudly but do NOT create PAUSED.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGDIR="$ROOT/loop/logs"
LOCK="$ROOT/loop/memory/run.lock"
PAUSED="$ROOT/loop/PAUSED"
KNOWLEDGE="$ROOT/loop/memory/KNOWLEDGE.md"
REFLECTIONS="$ROOT/loop/memory/reflections"
COST="$ROOT/loop/scripts/cost-log.sh"
FABLE_MODEL="claude-fable-5"
MAX_TOKENS=64000
REFLECT_TIMEOUT=900
TS="$(date +%Y%m%d-%H%M%S)"
RLOG="$LOGDIR/reflect-$TS.log"
TMP="$(mktemp -d)"

mkdir -p "$LOGDIR" "$REFLECTIONS"
log()   { printf '%s\n' "$*" >> "$RLOG"; }
alert() { echo "ALERT [reflect-$TS]: $*" >&2; log "alert=$*"; }
contain() { log "containment=$*"; alert "CONTAINMENT: $*"; }

# ---- rollback mode ----
if [ "${1:-}" = "--rollback" ]; then
  rec="${2:?usage: reflect.sh --rollback <record-file>}"
  [ -f "$rec" ] || { echo "reflect.sh: no such record: $rec" >&2; exit 1; }
  case "$(grep -m1 '^tier=' "$rec" | cut -d= -f2)" in
    1)
      # remove exactly the lines this record appended to KNOWLEDGE.md
      applied="$TMP/applied"; sed -n '/^--- applied lines ---$/,$p' "$rec" | tail -n +2 > "$applied"
      grep -vxF -f "$applied" "$KNOWLEDGE" > "$TMP/k" || true
      mv "$TMP/k" "$KNOWLEDGE"
      echo "reflect.sh: rolled back tier-1 record $(basename "$rec")"
      ;;
    2) echo "reflect.sh: tier-2 rollbacks are git reverts of the merged PR — nothing to do here" ;;
    *) echo "reflect.sh: record has no tier field" >&2; exit 1 ;;
  esac
  exit 0
fi

TEST_INPUT=""
if [ "${1:-}" = "--test-input" ]; then TEST_INPUT="${2:?--test-input needs a file}"; fi

run_with_timeout() {
  local secs="$1"; shift
  # <&0 re-attaches the caller's stdin: background jobs otherwise get /dev/null
  "$@" <&0 & local pid=$!
  ( sleep "$secs" && kill -TERM "$pid" 2>/dev/null ) & local dog=$!
  local rc=0; wait "$pid" || rc=$?
  kill "$dog" 2>/dev/null; wait "$dog" 2>/dev/null || true
  return "$rc"
}

reflect_failed() { # alert if this makes 3 consecutive failed nights; never PAUSE
  log "outcome=failure"
  local fails=0 f
  for f in $(ls -1 "$LOGDIR"/reflect-*.log 2>/dev/null | sort | tail -3); do
    grep -q '^outcome=failure' "$f" && fails=$((fails + 1))
  done
  if [ "$fails" -ge 3 ]; then
    alert "reflector has failed 3 nights running — it needs a human, but the work loop stays live (no PAUSED)"
  fi
  exit 1
}

log "reflect_id=$TS"

# ---- kill switch + lock (same discipline as loop.sh) ----
if [ -f "$PAUSED" ] && [ -z "$TEST_INPUT" ]; then log "outcome=paused-noop"; exit 0; fi
if [ -z "$TEST_INPUT" ]; then
  if [ -f "$LOCK" ] && [ $(( $(date +%s) - $(stat -f %m "$LOCK") )) -lt 7200 ]; then
    log "outcome=lock-held"; exit 0
  fi
  rm -f "$LOCK"
  trap 'rm -f "$LOCK"; rm -rf "$TMP"' EXIT INT TERM
  printf 'run_id=reflect-%s\nworktree=\n' "$TS" > "$LOCK"
  # one reflection per calendar day, hard-checked against logs/
  # (test-input runs don't count — they never called the API)
  for f in "$LOGDIR"/reflect-"$(date +%Y%m%d)"-*.log; do
    [ -f "$f" ] || continue
    [ "$f" = "$RLOG" ] && continue
    grep -q '^mode=test-input' "$f" && continue
    # only a SUCCESSFUL reflection consumes the day's slot; failures may retry,
    # and already-ran-today markers don't compound
    grep -q '^outcome=success' "$f" || continue
    log "outcome=already-ran-today"; exit 0
  done
else
  trap 'rm -rf "$TMP"' EXIT INT TERM
fi

# ---- get the model response ----
if [ -n "$TEST_INPUT" ]; then
  cp "$TEST_INPUT" "$TMP/proposals.json"
  log "mode=test-input"
else
  if [ -f "$ROOT/.env" ]; then set -a; . "$ROOT/.env"; set +a; fi
  {
    cat "$ROOT/loop/reflector.md"
    echo; echo '=== LAST 7 DAYS OF RUN LOGS ==='
    echo '<untrusted-input source="run logs">'
    find "$LOGDIR" -name 'run-*.log' -mtime -7 -exec cat {} + 2>/dev/null || true
    echo '</untrusted-input>'
    echo; echo '=== TRUST LEDGER ==='; cat "$ROOT/loop/memory/trust.tsv"
    echo; echo '=== GOAL LEDGER ==='; tail -50 "$ROOT/loop/memory/goal-ledger.tsv"
    echo; echo '=== COST (last entries) ==='; tail -50 "$ROOT/loop/memory/cost.tsv"
    echo; echo '=== CURRENT PROMPT AND SKILL FILES ==='
    for f in "$ROOT"/loop/triage.md "$ROOT"/loop/conductor.md "$ROOT"/loop/workers/*.md "$ROOT"/loop/skills/*.md; do
      echo "--- $f ---"; cat "$f"
    done
  } > "$TMP/prompt.txt"

  # effort HIGH, never xhigh — this is maintenance, not conducting.
  # Fallback disabled: --fallback-model is never passed.
  if ! run_with_timeout "$REFLECT_TIMEOUT" \
       env CLAUDE_CODE_MAX_OUTPUT_TOKENS="$MAX_TOKENS" \
       claude -p --model "$FABLE_MODEL" --effort high --allowedTools "" --output-format json \
       < "$TMP/prompt.txt" > "$TMP/envelope.json" 2> "$TMP/err"; then
    cat "$TMP/err" >> "$RLOG" 2>/dev/null || true
    alert "reflector call failed or timed out: $(head -2 "$TMP/err" 2>/dev/null)"
    reflect_failed
  fi
  # cost from actual usage fields
  in_tok="$(jq -r '.usage.input_tokens // empty' "$TMP/envelope.json" 2>/dev/null || true)"
  out_tok="$(jq -r '.usage.output_tokens // empty' "$TMP/envelope.json" 2>/dev/null || true)"
  dollars="$(jq -r '.total_cost_usd // empty' "$TMP/envelope.json" 2>/dev/null || true)"
  [ -z "$in_tok" ] && log "anomaly=missing-usage"
  "$COST" --log "$FABLE_MODEL" "${in_tok:-}" "${out_tok:-}" ${dollars:+"$dollars"}

  # step-9 validation
  cp "$TMP/envelope.json" "$LOGDIR/raw-reflect-$TS.json" 2>/dev/null || true
  jq -e . "$TMP/envelope.json" > /dev/null 2>&1 || { log "anomaly=unparseable-json"; alert "reflector JSON unparseable"; reflect_failed; }
  grep -q '"stop_reason"[[:space:]]*:[[:space:]]*"refusal"' "$TMP/envelope.json" && { log "anomaly=refusal"; alert "reflector REFUSED"; reflect_failed; }
  [ "$(jq -r '.is_error // false' "$TMP/envelope.json")" = "false" ] || { log "anomaly=error-envelope"; reflect_failed; }
  # reroute = the requested model is ABSENT (helper-model entries are normal)
  jq -e --arg m "$FABLE_MODEL" '(.modelUsage // {}) | keys[] | select(startswith($m))' "$TMP/envelope.json" > /dev/null 2>&1 \
    || { log "anomaly=reroute"; alert "reflector was not served by $FABLE_MODEL"; reflect_failed; }
  jq -r '.result // empty' "$TMP/envelope.json" | sed -n '/^```/!p' | awk '/{/ { seen = 1 } seen { print }' > "$TMP/proposals.json"
fi

jq -e '.proposals | type == "array"' "$TMP/proposals.json" > /dev/null 2>&1 || {
  log "anomaly=invalid-proposals-json"; alert "reflector output is not a proposals object"; reflect_failed
}

n="$(jq '.proposals | length' "$TMP/proposals.json")"
log "proposals=$n"
if [ "$n" -gt 3 ]; then contain "more than 3 proposals ($n) — processing only the first 3"; n=3; fi

# ---- path allowlist enforcement: the teeth ----
tier2_allowed() { # target -> 0 if allowed for tier 2
  case "$1" in
    loop/triage.md|loop/conductor.md) return 0 ;;
    loop/workers/*.md|loop/skills/*.md) return 0 ;;
    *) return 1 ;;
  esac
}

is_traversal() { case "$1" in /*|*..*) return 0 ;; *) return 1 ;; esac; }

knowledge_line_ok() { # single fact line -> 0 if safe
  local line="$1"
  case "$line" in
    *';'*|*'&'*|*'|'*|*'`'*|*'$'*|*'>'*|*'<'*) return 1 ;;
  esac
  printf '%s' "$line" | grep -qiE 'ignore|always run|execute|curl |wget |\bsh\b|\bbash\b' && return 1
  return 0
}

evidence_exists() { # run-id -> 0 if a matching log exists
  local id="${1#run-}"
  ls "$LOGDIR"/run-*"$id"*.log > /dev/null 2>&1
}

prompt_edits=0
i=0
while [ "$i" -lt "$n" ]; do
  p="$(jq -c ".proposals[$i]" "$TMP/proposals.json")"
  i=$((i + 1))
  tier="$(printf '%s' "$p" | jq -r '.tier // empty')"
  ptype="$(printf '%s' "$p" | jq -r '.type // empty')"
  target="$(printf '%s' "$p" | jq -r '.target // empty')"
  rationale="$(printf '%s' "$p" | jq -r '.rationale // empty')"

  if is_traversal "$target"; then
    contain "proposal $i targets '$target' — path traversal or absolute path, rejected"
    continue
  fi

  # tier claims are CHECKED: tier 1 is only ever KNOWLEDGE.md
  if [ "$tier" = "1" ] && [ "$target" != "loop/memory/KNOWLEDGE.md" ] && [ "$target" != "memory/KNOWLEDGE.md" ]; then
    if tier2_allowed "$target"; then
      contain "proposal $i claimed tier 1 for '$target' — tier claim overridden to 2 (PR path, never auto-apply)"
      tier=2
    else
      contain "proposal $i claimed tier 1 for protected/unknown path '$target' — rejected, nothing written"
      continue
    fi
  fi
  if [ "$tier" = "2" ] && ! tier2_allowed "$target"; then
    contain "proposal $i (tier 2) targets '$target' — outside the allowlist (protected file or unknown path), rejected"
    continue
  fi
  if [ "$tier" != "1" ] && [ "$tier" != "2" ]; then
    contain "proposal $i has tier '$tier' — rejected"
    continue
  fi

  # evidence: every cited run-id must actually exist in logs/
  ev_ok=yes
  while IFS= read -r ev; do
    [ -z "$ev" ] && continue
    evidence_exists "$ev" || ev_ok=no
  done < <(printf '%s' "$p" | jq -r '.evidence[]? // empty')
  [ "$(printf '%s' "$p" | jq -r '.evidence | length')" -gt 0 ] 2>/dev/null || ev_ok=no
  if [ "$ev_ok" = "no" ]; then
    contain "proposal $i cites no run-id that exists in logs/ — no evidence, no proposal"
    continue
  fi

  if [ "$tier" = "1" ]; then
    # append-only facts; each line filtered for instruction patterns
    applied="$TMP/applied-$i"; : > "$applied"
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      if knowledge_line_ok "$line"; then
        printf '%s\n' "$line" >> "$applied"
      else
        contain "KNOWLEDGE line rejected by instruction-pattern filter: ${line:0:80}"
      fi
    done < <(printf '%s' "$p" | jq -r '.patch')
    if [ -s "$applied" ]; then
      touch "$KNOWLEDGE"
      cat "$applied" >> "$KNOWLEDGE"
      tail -150 "$KNOWLEDGE" > "$TMP/k" && mv "$TMP/k" "$KNOWLEDGE"   # 150-line cap, prune oldest
      rec="$REFLECTIONS/$TS-p$i.record"
      {
        echo "timestamp=$TS"; echo "tier=1"; echo "target=loop/memory/KNOWLEDGE.md"
        echo "rationale=$rationale"
        echo "evidence=$(printf '%s' "$p" | jq -c '.evidence')"
        echo "--- applied lines ---"; cat "$applied"
      } > "$rec"
      log "applied=tier1 lines=$(wc -l < "$applied" | tr -d ' ') record=$(basename "$rec")"
    fi
  else
    if [ "$ptype" = "prompt-fix" ]; then
      prompt_edits=$((prompt_edits + 1))
      if [ "$prompt_edits" -gt 1 ]; then
        contain "proposal $i is a second prompt-edit tonight — max 1, rejected"
        continue
      fi
    fi
    patch_lines="$(printf '%s' "$p" | jq -r '.patch' | wc -l | tr -d ' ')"
    if [ "$patch_lines" -gt 40 ]; then
      contain "proposal $i patch is $patch_lines lines (>40) — rejected; brains change in small diffs"
      continue
    fi
    branch="agentic/self-improve-$TS-$i"
    wt="$TMP/si-wt-$i"
    git -C "$ROOT" worktree add -b "$branch" "$wt" HEAD > /dev/null 2>&1
    patch_body="$TMP/patch-$i"; printf '%s' "$p" | jq -r '.patch' > "$patch_body"
    if head -1 "$patch_body" | grep -qE '^(--- |diff --git)'; then
      if ! git -C "$wt" apply "$patch_body" 2>> "$RLOG"; then
        contain "proposal $i unified diff did not apply — rejected"
        git -C "$ROOT" worktree remove --force "$wt" 2>/dev/null || true
        continue
      fi
    else
      cp "$patch_body" "$wt/$target"
    fi
    changed_files="$(git -C "$wt" status --porcelain | wc -l | tr -d ' ')"
    if [ "$changed_files" -ne 1 ]; then
      contain "proposal $i touches $changed_files files (must be exactly 1) — rejected"
      git -C "$ROOT" worktree remove --force "$wt" 2>/dev/null || true
      continue
    fi
    git -C "$wt" add -A && git -C "$wt" commit -q -m "agentic self-improve: $target ($TS)"
    gh label create "agentic:self-improve" --color d93f0b 2>/dev/null || true
    body="$TMP/body-$i"
    {
      echo "Reflector self-improvement proposal (tier 2 — requires approve.sh)."
      echo; echo "Rationale: $rationale"
      echo "Evidence run-ids: $(printf '%s' "$p" | jq -r '.evidence | join(", ")')"
      echo; echo "Verify the cited runs actually show the problem this patch claims to fix."
    } > "$body"
    if git -C "$wt" push -q -u origin "$branch" && \
       gh pr create --draft --head "$branch" --label "agentic:self-improve" \
         --title "self-improve: $target ($TS)" --body-file "$body" >> "$RLOG" 2>&1; then
      rec="$REFLECTIONS/$TS-p$i.record"
      {
        echo "timestamp=$TS"; echo "tier=2"; echo "target=$target"; echo "branch=$branch"
        echo "rationale=$rationale"
        echo "evidence=$(printf '%s' "$p" | jq -c '.evidence')"
        echo "--- patch ---"; cat "$patch_body"
      } > "$rec"
      log "applied=tier2-pr target=$target branch=$branch record=$(basename "$rec")"
    else
      log "anomaly=self-improve-pr-failed target=$target"
      alert "could not open self-improve draft PR for $target"
    fi
    git -C "$ROOT" worktree remove --force "$wt" 2>/dev/null || true
  fi
done

# ---- protected observations -> digest, verbatim, flagged ----
obs_n="$(jq -r '.protected_observations // [] | length' "$TMP/proposals.json")"
if [ "$obs_n" -gt 0 ]; then
  jq -r '.protected_observations[]' "$TMP/proposals.json" | sed 's/^/⚠ reflector: /' \
    > "$REFLECTIONS/$TS.protected-observations"
  log "protected_observations=$obs_n"
fi

log "outcome=success"
echo "reflect.sh: done — $n proposal(s) processed; see $(basename "$RLOG")"
