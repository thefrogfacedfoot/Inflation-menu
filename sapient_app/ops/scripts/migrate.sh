#!/usr/bin/env bash
# Idempotent migration runner. Order:
#   1. finder        sqlalchemy create_all() (public schema)
#   2. visibility    *.sql in visibility/migrations/ in lexical order
#   3. dashboard     drizzle-kit push
#
# Each step MUST be safe to re-run. We re-run all three on every deploy.
#
# Usage:
#   DATABASE_URL=postgres://... ops/scripts/migrate.sh
#   ops/scripts/migrate.sh --only=visibility
set -euo pipefail

ONLY="${1:-}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "DATABASE_URL must be set" >&2
    exit 2
fi

# Derive a psql-compatible URL from the sqlalchemy form (postgresql+psycopg://…)
# so step (2) below can pipe SQL straight in. Drizzle and finder accept the
# original; only psql needs the canonical scheme.
PSQL_URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"

step_finder() {
    echo "==> finder: sqlalchemy create_all()"
    cd "$REPO_ROOT"
    python -c "from app.db import init_db; init_db()"
}

step_visibility() {
    echo "==> visibility: SQL migrations"
    local files
    # LC_ALL=C makes the sort stable across locales — important when filenames
    # contain digits or punctuation that re-order under en_US.
    files=$(LC_ALL=C ls "$REPO_ROOT/visibility/migrations" | grep -E '\.sql$' | sort)
    if [[ -z "$files" ]]; then
        echo "    (no .sql files found, skipping)"
        return
    fi
    for f in $files; do
        echo "    applying $f"
        psql "$PSQL_URL" -v ON_ERROR_STOP=1 -f "$REPO_ROOT/visibility/migrations/$f"
    done
}

step_dashboard() {
    echo "==> dashboard: drizzle push"
    cd "$REPO_ROOT/dashboard"
    # `db:push` is idempotent — it diffs the live schema and emits only the
    # missing DDL. No version table to advance.
    npm run db:push
}

case "$ONLY" in
    "")
        step_finder
        step_visibility
        step_dashboard
        ;;
    --only=finder)     step_finder ;;
    --only=visibility) step_visibility ;;
    --only=dashboard)  step_dashboard ;;
    *)
        echo "unknown arg: $ONLY (expected --only=finder|visibility|dashboard)" >&2
        exit 2
        ;;
esac

echo "==> migrations done"
