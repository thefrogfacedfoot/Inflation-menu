#!/usr/bin/env bash
# Guardrail with VETO power: flag credential-shaped content in a diff.
# Takes a worktree path (scans its diff vs HEAD, new files included) or a
# unified-diff file. Any hit = exit 1 with the match location.
# Simple grep patterns by design — this catches the common failure.
set -euo pipefail

TARGET="${1:?usage: scan-secrets.sh <worktree-path|diff-file>}"

DIFF_FILE="$(mktemp)"
trap 'rm -f "$DIFF_FILE"' EXIT

if [ -d "$TARGET" ]; then
  git -C "$TARGET" add -N . >/dev/null 2>&1 || true   # make new files diff-visible
  git -C "$TARGET" diff HEAD > "$DIFF_FILE"
else
  cat -- "$TARGET" > "$DIFF_FILE"
fi

found=0

scan() { # $1=pattern $2=description $3=optional grep flags
  local hits
  hits="$(grep -nE ${3:-} -- "$1" "$DIFF_FILE" | grep -E '^[0-9]+:\+' | grep -Ev '^[0-9]+:\+\+\+' || true)"
  if [ -n "$hits" ]; then
    found=1
    echo "scan-secrets: HIT ($2) at diff line:"
    echo "$hits"
  fi
}

scan '(^|[^A-Za-z0-9_])sk-[A-Za-z0-9_-]{8,}'                 'sk- key prefix'
scan 'AKIA[0-9A-Z]{16}'                                      'AWS access key'
scan '(^|[^A-Za-z0-9_])ghp_[A-Za-z0-9]{20,}'                 'GitHub token'
scan '(^|[^A-Za-z0-9_])xox[baprs]-[A-Za-z0-9][A-Za-z0-9-]{8,}' 'Slack token'
scan '\-\-\-\-\-BEGIN [A-Z ]*PRIVATE KEY\-\-\-\-\-'          'private key header'
scan '(secret|token|passwd|password|credential|api[_-]?key|apikey|private[_-]?key)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][A-Za-z0-9+/=_-]{20,}' 'credential-named variable with long literal' '-i'

# New or modified .env* files anywhere in the diff.
ENVFILES="$(grep -nE '^\+\+\+ .*/\.env' "$DIFF_FILE" || true)"
if [ -n "$ENVFILES" ]; then
  found=1
  echo "scan-secrets: HIT (.env file in diff):"
  echo "$ENVFILES"
fi

if [ "$found" -ne 0 ]; then
  echo "scan-secrets: FAIL — credential-shaped content found" >&2
  exit 1
fi
echo "scan-secrets: clean"
