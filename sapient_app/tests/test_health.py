"""Schema-aware /health probe for the finder service.

The endpoint returns:
  - 200 {"status":"ok"} when the schema check passes
  - 503 {"status":"error","check":"<reason>"} otherwise

We monkeypatch _schema_check so the route's wiring is exercised without
needing a real Postgres to drop a table out from under us."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as finder_main


def test_health_ok_when_schema_present(monkeypatch) -> None:
    monkeypatch.setattr(finder_main, "_schema_check", lambda: (True, None))
    client = TestClient(finder_main.app)
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body == {"status": "ok", "service": "finder"}


def test_health_503_names_the_failed_check(monkeypatch) -> None:
    monkeypatch.setattr(
        finder_main,
        "_schema_check",
        lambda: (False, "public.opportunities missing"),
    )
    client = TestClient(finder_main.app)
    res = client.get("/health")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "error"
    assert body["service"] == "finder"
    assert body["check"] == "public.opportunities missing"


def test_schema_check_against_real_engine_initially_passes() -> None:
    """conftest calls init_db() — the table exists, so the inspect()-based
    probe should return ok. We invoke _schema_check directly rather than
    through the route because FastAPI's sync handler runs in a worker
    thread, and the SQLite in-memory engine's SingletonThreadPool would
    hand the worker thread a fresh empty DB. inspect()-against-prod-Postgres
    has no such quirk."""
    ok, reason = finder_main._schema_check()
    assert ok, f"unexpected schema failure: {reason}"
