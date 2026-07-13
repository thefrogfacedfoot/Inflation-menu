#!/usr/bin/env bash
# Guardrail: run this repo's real checks against a worktree and enforce diff hygiene.
# The repo's checks are HARDCODED by inspection (2026-07-13):
#   1. cd sapient_app && python3 -m pytest -q     (17 tests at build time)
#   2. cd dashboard  && npx tsc --noEmit
# A worktree missing either suite fails loudly — never silently passes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WT="${1:?usage: verify.sh <worktree-path>}"
WT="$(cd -- "$WT" && pwd)"
MAX_DIFF_LINES=400
LOCKFILE_RE='(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Cargo\.lock|Gemfile\.lock)($|	)'

fail() { echo "verify.sh: FAIL: $*" >&2; exit 1; }

git -C "$WT" rev-parse --git-dir >/dev/null 2>&1 || fail "not a git worktree: $WT"

# S3(a): every changed or new path must stay inside the worktree.
while IFS= read -r p; do
  [ -z "$p" ] && continue
  case "$p" in
    /*|../*|*/../*|*/..|..) fail "path escapes worktree: $p" ;;
  esac
done < <(git -C "$WT" diff HEAD --name-only; git -C "$WT" ls-files --others --exclude-standard)

# S3(b): the main checkout must be untouched (runtime loop state exempt).
if [ "$WT" != "$ROOT" ]; then
  DIRTY="$(git -C "$ROOT" diff --name-only HEAD -- . ':(exclude)loop/memory' ':(exclude)loop/logs' || true)"
  [ -z "$DIRTY" ] || fail "files changed outside the worktree: $DIRTY"
fi

# Contract: diff size limit. Lockfiles excluded from the COUNT only —
# scan-secrets.sh still sees them in full.
CHANGED="$(git -C "$WT" diff HEAD --numstat | { grep -Ev "$LOCKFILE_RE" || true; } | awk '{ a=$1; d=$2; if (a=="-") a=0; if (d=="-") d=0; s+=a+d } END { print s+0 }')"
[ "$CHANGED" -le "$MAX_DIFF_LINES" ] || fail "diff is $CHANGED lines; contract limit is $MAX_DIFF_LINES"

# Real check 1: sapient_app test suite. Absence is a loud failure.
[ -f "$WT/sapient_app/pytest.ini" ] || fail "sapient_app test suite missing from worktree"
( cd "$WT/sapient_app" && python3 -m pytest -q ) || fail "sapient_app pytest failed"

# Real check 2: dashboard typecheck. node_modules is borrowed read-only from
# the main checkout (workers may never add dependencies, so it cannot drift).
[ -f "$WT/dashboard/tsconfig.json" ] || fail "dashboard tsconfig missing from worktree"
[ -e "$WT/dashboard/node_modules" ] || ln -s "$ROOT/dashboard/node_modules" "$WT/dashboard/node_modules"
( cd "$WT/dashboard" && npx tsc --noEmit ) || fail "dashboard typecheck failed"

echo "verify.sh: PASS"
