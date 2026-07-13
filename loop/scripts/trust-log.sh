#!/usr/bin/env bash
# Trust ledger over loop/memory/trust.tsv (4 columns: skill, runs, passes, human_approvals).
#
# Tiers:
#   auto  = runs >= 20 AND pass rate >= 95% AND human_approvals >= 5
#           (the approvals gate is the point: a skill cannot reach unattended
#            shipping on self-graded passes alone — a human must have reviewed
#            and approved at least 5 of its queued drafts via approve.sh)
#   watch = runs < 10 OR pass rate < 90%   (draft-only)
#   queue = everything else
# Demotion: an established skill (10+ runs) dropping below 90% alerts on stderr
# AND resets human_approvals to 0 — it re-earns the gate.
#
# --approve is called ONLY by approve.sh, never by loop.sh. Merging a PR in the
# GitHub UI grants no trust credit.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TSV="$ROOT/loop/memory/trust.tsv"
[ -f "$TSV" ] || { echo "trust-log.sh: missing $TSV" >&2; exit 1; }

usage() { echo "usage: trust-log.sh --log <skill> pass|fail | --render | --tier <skill> | --approve <skill>" >&2; exit 2; }

read_row() { # skill -> "runs passes approvals" or empty
  awk -F'\t' -v s="$1" '$1 == s { print $2, $3, $4 }' "$TSV"
}

write_row() { # skill runs passes approvals — update in place or append
  local skill="$1" runs="$2" passes="$3" appr="$4" tmp
  tmp="$(mktemp)"
  awk -F'\t' -v OFS='\t' -v s="$skill" -v r="$runs" -v p="$passes" -v a="$appr" '
    $1 == s { print s, r, p, a; found = 1; next }
    { print }
    END { if (!found) print s, r, p, a }
  ' "$TSV" > "$tmp"
  mv "$tmp" "$TSV"
}

tier_of() { # runs passes approvals
  local runs="$1" passes="$2" appr="$3"
  if [ "$runs" -ge 20 ] && [ $((passes * 100)) -ge $((runs * 95)) ] && [ "$appr" -ge 5 ]; then
    echo auto
  elif [ "$runs" -lt 10 ] || [ $((passes * 100)) -lt $((runs * 90)) ]; then
    echo watch
  else
    echo queue
  fi
}

case "${1:-}" in
  --log)
    skill="${2:?skill required}"; result="${3:?pass|fail required}"
    case "$result" in pass|fail) ;; *) usage ;; esac
    read -r runs passes appr <<< "$(read_row "$skill")" || true
    runs="${runs:-0}"; passes="${passes:-0}"; appr="${appr:-0}"
    runs=$((runs + 1))
    [ "$result" = "pass" ] && passes=$((passes + 1))
    if [ "$runs" -ge 10 ] && [ $((passes * 100)) -lt $((runs * 90)) ] && [ "$appr" -gt 0 ]; then
      echo "trust-log.sh: DEMOTION: $skill dropped below 90% pass rate ($passes/$runs); human_approvals reset to 0 — it re-earns the gate" >&2
      appr=0
    fi
    write_row "$skill" "$runs" "$passes" "$appr"
    ;;
  --render)
    printf '%-20s %5s %6s %9s %6s\n' skill runs passes approvals tier
    while IFS=$'\t' read -r skill runs passes appr; do
      case "$skill" in ''|\#*) continue ;; esac
      printf '%-20s %5s %6s %9s %6s\n' "$skill" "$runs" "$passes" "$appr" "$(tier_of "$runs" "$passes" "$appr")"
    done < "$TSV"
    ;;
  --tier)
    skill="${2:?skill required}"
    read -r runs passes appr <<< "$(read_row "$skill")" || true
    tier_of "${runs:-0}" "${passes:-0}" "${appr:-0}"
    ;;
  --approve)
    skill="${2:?skill required}"
    read -r runs passes appr <<< "$(read_row "$skill")" || true
    write_row "$skill" "${runs:-0}" "${passes:-0}" "$(( ${appr:-0} + 1 ))"
    ;;
  *) usage ;;
esac
