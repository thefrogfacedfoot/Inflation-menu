"""Test environment bootstrap. Must set env BEFORE any `visibility` import,
because db.py reads DATABASE_URL/VISIBILITY_DB_SCHEMA at module load."""
import os
import sys
from pathlib import Path

# Make `visibility` importable when running `pytest` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("VISIBILITY_DB_SCHEMA", "")  # SQLite has no schemas
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")
os.environ.setdefault("PERPLEXITY_API_KEY", "test-key")
os.environ.setdefault("COST_CAP_WEBHOOK_URL", "")

import pytest  # noqa: E402

from visibility import db as _db  # noqa: E402
from visibility import models  # noqa: F401,E402  ensure tables registered


@pytest.fixture
def session():
    """Fresh in-memory SQLite per test (created here, dropped on close)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:", future=True)
    _db.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    s = Session()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()
