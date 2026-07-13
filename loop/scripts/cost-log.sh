#!/usr/bin/env bash
# Cost ledger over loop/memory/cost.tsv:
#   timestamp  model  input_tokens  output_tokens  dollars  note
#
# --log <model> <input_tokens> <output_tokens> [reported_dollars]
#   Dollars come from ACTUAL usage fields the caller parsed out of the API
#   response. Pricing (per million tokens): claude-fable-5 $10/$50,
#   claude-haiku-4-5 $1/$5. Other models must pass reported_dollars.
#   Missing or non-numeric usage is an ANOMALY logged at a pessimistic
#   estimate — never as zero.
# --today | --month : sum of dollars for the current day / calendar month.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TSV="$ROOT/loop/memory/cost.tsv"
[ -f "$TSV" ] || { echo "cost-log.sh: missing $TSV" >&2; exit 1; }

PESSIMISTIC_DOLLARS="5.2000"   # ~200k in + 64k out at Fable prices

is_num() { case "$1" in ''|*[!0-9]*) return 1 ;; *) return 0 ;; esac; }

case "${1:-}" in
  --log)
    model="${2:?model required}"; in_tok="${3:-}"; out_tok="${4:-}"; reported="${5:-}"
    ts="$(date '+%Y-%m-%dT%H:%M:%S')"
    note="ok"
    if ! is_num "$in_tok" || ! is_num "$out_tok"; then
      in_tok="${in_tok:--}"; out_tok="${out_tok:--}"
      dollars="$PESSIMISTIC_DOLLARS"
      note="anomaly-missing-usage-pessimistic-estimate"
    elif [ -n "$reported" ]; then
      dollars="$reported"
    else
      case "$model" in
        claude-fable-5)    in_rate=10; out_rate=50 ;;
        claude-haiku-4-5*) in_rate=1;  out_rate=5  ;;
        *)
          dollars="$PESSIMISTIC_DOLLARS"
          note="anomaly-unknown-model-pessimistic-estimate"
          ;;
      esac
      if [ "$note" = "ok" ]; then
        dollars="$(awk -v i="$in_tok" -v o="$out_tok" -v ir="$in_rate" -v or="$out_rate" \
          'BEGIN { printf "%.4f", (i * ir + o * or) / 1000000 }')"
      fi
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$ts" "$model" "$in_tok" "$out_tok" "$dollars" "$note" >> "$TSV"
    ;;
  --today)
    day="$(date '+%Y-%m-%d')"
    awk -F'\t' -v d="$day" '$1 ~ "^"d { s += $5 } END { printf "%.4f\n", s + 0 }' "$TSV"
    ;;
  --month)
    month="$(date '+%Y-%m')"
    awk -F'\t' -v m="$month" '$1 ~ "^"m { s += $5 } END { printf "%.4f\n", s + 0 }' "$TSV"
    ;;
  *)
    echo "usage: cost-log.sh --log <model> <in_tokens> <out_tokens> [reported_dollars] | --today | --month" >&2
    exit 2
    ;;
esac
