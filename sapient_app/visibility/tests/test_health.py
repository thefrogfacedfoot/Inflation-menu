"""Schema-aware /health probe for the visibility service.

Mirrors the finder's test_health.py — 200 on the happy path, 503 with the
failing check name when the schema isn't there. We monkeypatch
_schema_check so the route's wiring is exercised without dropping tables
under a live engine.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from visibility import api as visibility_api


def test_health_ok_when_schema_present(monkeypatch) -> None:
    monkeypatch.setattr(visibility_api, "_schema_check", lambda: (True, None))
    client = TestClient(visibility_api.app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "visibility"}


def test_health_503_names_the_failed_check(monkeypatch) -> None:
    monkeypatch.setattr(
        visibility_api,
        "_schema_check",
        lambda: (False, "visibility.runs missing"),
    )
    client = TestClient(visibility_api.app)
    res = client.get("/health")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "error"
    assert body["service"] == "visibility"
    assert body["check"] == "visibility.runs missing"


def test_schema_check_against_real_engine() -> None:
    """conftest's `session` fixture builds a side engine; the route's
    _schema_check inspects the module-level visibility.db.engine. Bootstrap
    the tables there once so the inspect() probe has something to find.
    Confirms the route's wiring works against the live engine with
    SCHEMA=None (test mode) — runs lives in the default namespace."""
    from visibility.db import Base, engine

    Base.metadata.create_all(engine)
    ok, reason = visibility_api._schema_check()
    assert ok, f"unexpected schema failure: {reason}"
