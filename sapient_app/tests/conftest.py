"""Finder test environment. Settings reads required env vars at import
time — set sensible defaults before any `app` import lands."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("REDDIT_CLIENT_ID", "test")
os.environ.setdefault("REDDIT_CLIENT_SECRET", "test")
os.environ.setdefault("REDDIT_USER_AGENT", "test/0.1")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("PRODUCT_NAME", "TestProd")
os.environ.setdefault(
    "PRODUCT_DESCRIPTION", "A product used in tests; harmless."
)
os.environ.setdefault("PROBLEM_KEYWORDS", "")
os.environ.setdefault("SEED_SUBREDDITS", "testsub")
os.environ.setdefault("DISCOVER_ADJACENT_SUBREDDITS", "false")
os.environ.setdefault("DRY_RUN", "true")
os.environ.setdefault("MIN_SCORE_TO_STORE", "60")

# Materialize the in-memory SQLite schema so poller's existence check
# against opportunities doesn't fail with "no such table".
from app.db import init_db  # noqa: E402

init_db()
