#!/usr/bin/env bash
# Standing-goal checker. Runs each goal file's predicate (60s timeout), updates
# status/last-pass in place, appends to goal-ledger.tsv. ANY violation exits 1,
# lists the broken goals, AND creates loop/PAUSED — a violated invariant means
# stop shipping, not just send an email. Retiring a goal is a human decision.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GOALS_DIR="$ROOT/loop/goals"
LEDGER="$ROOT/loop/memory/goal-ledger.tsv"
PAUSED="$ROOT/loop/PAUSED"
NOW="$(date '+%Y-%m-%d')"

run_with_timeout() {
  local secs="$1"; shift
  "$@" <&0 & local pid=$!
  ( sleep "$secs" && kill -TERM "$pid" 2>/dev/null ) & local dog=$!
  local rc=0; wait "$pid" || rc=$?
  kill "$dog" 2>/dev/null; wait "$dog" 2>/dev/null || true
  return "$rc"
}

broken=()
checked=0

for goal in "$GOALS_DIR"/*.goal; do
  [ -f "$goal" ] || continue
  predicate="$(grep -m1 '^predicate:' "$goal" | cut -d: -f2- | sed 's/^ *//')"
  [ -n "$predicate" ] || { echo "verify-goals: $goal has no predicate — that is itself a violation" >&2; broken+=("$goal"); continue; }
  checked=$((checked + 1))
  if ( cd "$ROOT" && run_with_timeout 60 bash -c "$predicate" > /dev/null 2>&1 ); then
    status=satisfied
    sed -i '' -e "s/^status:.*/status: satisfied/" -e "s/^last-pass:.*/last-pass: $NOW/" "$goal"
  else
    status=VIOLATED
    sed -i '' -e "s/^status:.*/status: VIOLATED/" "$goal"
    broken+=("$goal")
  fi
  printf '%s\t%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$(basename "$goal")" "$status" >> "$LEDGER"
done

if [ "${#broken[@]}" -gt 0 ]; then
  echo "verify-goals: ⛔ STANDING GOAL VIOLATED:" >&2
  printf '  %s\n' "${broken[@]}" >&2
  printf '%s: standing goal violated: %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "${broken[*]}" > "$PAUSED"
  echo "verify-goals: loop/PAUSED created — no further runs until a human deletes it. Do not auto-fix." >&2
  exit 1
fi

echo "verify-goals: $checked goal(s) checked, all satisfied"
