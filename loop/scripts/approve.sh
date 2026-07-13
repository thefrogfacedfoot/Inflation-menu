#!/usr/bin/env bash
# The approval ritual. Queued work lives as DRAFT PRs labeled agentic:<skill>.
# This script lists them, shows each diff, and on your confirmation marks the
# PR ready AND credits the skill via trust-log.sh --approve.
#
# APPROVAL AND TRUST-CREDIT ARE ONE ACTION. Merging a draft in the GitHub UI
# out-of-band grants NO trust credit — only this script calls --approve, so the
# human gate cannot be skipped. Self-improvement PRs (agentic:self-improve) can
# be approved here but never earn work-skill trust credit.
#
# usage: approve.sh [pr-number]   (no arg = walk the whole queue)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TRUST="$ROOT/loop/scripts/trust-log.sh"

prs="$(gh pr list --draft --json number,title,labels \
  --jq '.[] | select(any(.labels[]; .name | startswith("agentic:"))) | "\(.number)\t\(.title)\t\([.labels[].name | select(startswith("agentic:"))] | first)"')"

if [ -n "${1:-}" ]; then
  prs="$(printf '%s\n' "$prs" | awk -F'\t' -v n="$1" '$1 == n')"
  [ -n "$prs" ] || { echo "approve.sh: PR #$1 is not an open agentic draft" >&2; exit 1; }
fi

if [ -z "$prs" ]; then
  echo "approve.sh: queue is empty — no open draft PRs with an agentic:* label"
  exit 0
fi

while IFS=$'\t' read -r number title label; do
  [ -z "$number" ] && continue
  skill="${label#agentic:}"
  echo "=============================================================="
  echo "PR #$number  [$label]  $title"
  echo "--------------------------------------------------------------"
  gh pr diff "$number" | head -300
  echo "--------------------------------------------------------------"
  printf 'Mark ready + credit trust for skill "%s"? [y/N] ' "$skill"
  read -r answer < /dev/tty
  case "$answer" in
    y|Y)
      gh pr ready "$number"
      if [ "$skill" = "self-improve" ]; then
        echo "approve.sh: #$number marked ready (self-improve: no work-skill trust credit)"
      else
        "$TRUST" --approve "$skill"
        echo "approve.sh: #$number marked ready; trust credited to $skill"
      fi
      ;;
    *) echo "approve.sh: #$number skipped" ;;
  esac
done <<< "$prs"
