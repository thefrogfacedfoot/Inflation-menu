#!/usr/bin/env bash
# Weekly digest — the review ritual that makes the 30-day shakedown real.
# Summarizes the last 7 days from logs/, cost.tsv, trust.tsv, goal-ledger.tsv:
# runs, decisions, pass/fail per skill, spend, anomalies, pending queue.
# Cron emails this weekly. If you read nothing else, read this.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS="$ROOT/loop/logs"
COST="$ROOT/loop/memory/cost.tsv"
GOALS="$ROOT/loop/memory/goal-ledger.tsv"

echo "AGENTIC-OS WEEKLY DIGEST — $(date '+%Y-%m-%d %H:%M')"
echo "================================================================"

recent_logs="$(find "$LOGS" -name 'run-*.log' -mtime -7 2>/dev/null | sort || true)"

echo ""
echo "## Runs (last 7 days)"
if [ -z "$recent_logs" ]; then
  echo "no runs logged"
else
  echo "total: $(printf '%s\n' "$recent_logs" | wc -l | tr -d ' ')"
  echo ""
  echo "## Decisions and outcomes"
  while IFS= read -r log; do
    run_id="$(grep -m1 '^run_id=' "$log" | cut -d= -f2- || true)"
    decision="$(grep -m1 '^decision=' "$log" | cut -d= -f2- || true)"
    skill="$(grep -m1 '^skill=' "$log" | cut -d= -f2- || true)"
    outcome="$(grep -m1 '^outcome=' "$log" | cut -d= -f2- || true)"
    printf '%-28s decision=%-8s skill=%-18s outcome=%s\n' \
      "${run_id:-$(basename "$log")}" "${decision:--}" "${skill:--}" "${outcome:--}"
  done <<< "$recent_logs"
  echo ""
  echo "## Pass/fail per skill (last 7 days)"
  grep -h '^skill=\|^outcome=' $recent_logs 2>/dev/null | paste - - 2>/dev/null | \
    awk -F'\t' '{ gsub(/skill=|outcome=/, ""); counts[$1"\t"$2]++ }
      END { for (k in counts) { split(k, a, "\t"); printf "%-20s %-10s %d\n", a[1], a[2], counts[k] } }' \
    || echo "no per-skill data"
  echo ""
  echo "## Anomalies (refusals, reroutes, truncations, injection-attempts, oversize)"
  grep -h '^anomaly=' $recent_logs 2>/dev/null | sort | uniq -c || echo "none"
fi

echo ""
echo "## Spend"
echo "today: \$$("$ROOT/loop/scripts/cost-log.sh" --today)   month: \$$("$ROOT/loop/scripts/cost-log.sh" --month)"
week_spend="$(awk -F'\t' -v cutoff="$(date -v-7d '+%Y-%m-%d' 2>/dev/null || date -d '7 days ago' '+%Y-%m-%d')" \
  '$1 >= cutoff { s += $5 } END { printf "%.4f", s + 0 }' "$COST")"
echo "last 7 days: \$$week_spend"

echo ""
echo "## Trust ledger"
"$ROOT/loop/scripts/trust-log.sh" --render

echo ""
echo "## Goal ledger (most recent entries)"
if [ -s "$GOALS" ]; then tail -10 "$GOALS"; else echo "no goal checks recorded"; fi

echo ""
echo "## Pending queue (draft PRs labeled agentic:*)"
if queue="$(gh pr list --draft --json number,title,labels \
  --jq '[.[] | select(any(.labels[]; .name | startswith("agentic:")))] | length' 2>&1)"; then
  echo "pending: $queue draft PR(s) — review with approve.sh"
else
  echo "queue count UNAVAILABLE — gh failed: $queue"
fi

echo ""
echo "## Protected-file observations from the reflector (⚠ review by hand)"
obs="$(find "$ROOT/loop/memory/reflections" -name '*.protected-observations' -mtime -7 2>/dev/null || true)"
if [ -n "$obs" ]; then cat $obs; else echo "none"; fi

echo ""
echo "================================================================"
echo "Kill switch: $([ -f "$ROOT/loop/PAUSED" ] && echo "⛔ PAUSED — read the newest log before deleting loop/PAUSED" || echo "not set (system live)")"
