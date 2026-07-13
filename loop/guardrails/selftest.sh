#!/usr/bin/env bash
# The canary. Plants a broken test and a fake key in a temp worktree and
# asserts BOTH guardrails catch them. Runs weekly via cron forever —
# guardrails rot, and an untested guardrail is a decoration.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_BASE="$(mktemp -d)"
WT="$TMP_BASE/selftest-wt"
trap 'git -C "$ROOT" worktree remove --force "$WT" >/dev/null 2>&1 || true; rm -rf "$TMP_BASE"' EXIT

git -C "$ROOT" worktree add --detach "$WT" HEAD >/dev/null 2>&1

# Plant (a): break the test suite.
echo 'raise RuntimeError("selftest planted failure")' >> "$WT/sapient_app/app/__init__.py"
if "$ROOT/loop/guardrails/verify.sh" "$WT" >/dev/null 2>&1; then
  echo "SELFTEST FAILURE: verify.sh PASSED a worktree with a broken test suite. The guardrail is rotten. Do not trust green runs until this is fixed." >&2
  exit 1
fi
git -C "$WT" checkout -- sapient_app/app/__init__.py

# Plant (b): a fake sk- key in a config file. Assembled at runtime so THIS
# file never contains a contiguous key pattern and cannot trip the scanner.
PLANT_KEY="sk-""selftestFAKEkey1234567890abcd"
printf 'api_key = "%s"\n' "$PLANT_KEY" >> "$WT/sapient_app/app/config.py"
if "$ROOT/loop/guardrails/scan-secrets.sh" "$WT" >/dev/null 2>&1; then
  echo "SELFTEST FAILURE: scan-secrets.sh passed a planted sk- key. The secrets veto is rotten. Do not ship anything until this is fixed." >&2
  exit 1
fi

echo "selftest: PASS — verify.sh caught the broken test, scan-secrets.sh caught the planted key"
