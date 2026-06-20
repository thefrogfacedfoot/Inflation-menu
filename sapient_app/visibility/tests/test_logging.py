"""Coverage for ops/logging/python/middleware.py and the visibility counters
it lives alongside. The middleware is shared by finder + visibility — this
file tests it via the visibility import path because conftest already wires
sys.path for ops/logging/python via visibility._obs.

Specifically:
  - CorrelationIdMiddleware reads X-Correlation-Id when present
  - CorrelationIdMiddleware generates a UUID4 when absent
  - the response echoes the id back
  - structlog log lines include correlation_id + service + ISO timestamp
  - counters (cost cap, runs, cross-schema link failures) increment
    on the matching failure paths via fake requests
"""
from __future__ import annotations

import io
import json
import logging
import re
import uuid

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Importing visibility._obs first prepends ops/logging/python to sys.path
# so the bare `import middleware` below works.
from visibility import _obs  # noqa: F401
from middleware import CorrelationIdMiddleware, configure_structlog, correlation_id_var
from visibility.metrics import (
    visibility_cost_cap_short_circuits_total,
    visibility_cross_schema_link_failures_total,
    visibility_runs_total,
)


UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


# ----- middleware behaviour ---------------------------------------------------


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str | None]:
        return {"cid": correlation_id_var.get()}

    return app


def test_middleware_uses_incoming_header() -> None:
    client = TestClient(_app())
    sent = "11111111-2222-3333-4444-555555555555"
    res = client.get("/ping", headers={"X-Correlation-Id": sent})
    assert res.status_code == 200
    assert res.json() == {"cid": sent}
    assert res.headers["x-correlation-id"] == sent


def test_middleware_generates_uuid_when_absent() -> None:
    client = TestClient(_app())
    res = client.get("/ping")
    assert res.status_code == 200
    cid = res.json()["cid"]
    assert cid is not None
    assert UUID_RE.match(cid), f"not a UUID4: {cid}"
    # confirm it's parseable
    uuid.UUID(cid)
    assert res.headers["x-correlation-id"] == cid


def test_middleware_does_not_leak_id_across_requests() -> None:
    client = TestClient(_app())
    r1 = client.get("/ping", headers={"X-Correlation-Id": "abc-111"})
    r2 = client.get("/ping")
    assert r1.json()["cid"] == "abc-111"
    assert r2.json()["cid"] != "abc-111"


# ----- structlog plumbing -----------------------------------------------------


def _capture_log_line(service: str = "visibility") -> dict:
    """Configure structlog to write JSON to a buffer, emit one line under a
    correlation_id, and return the parsed dict."""
    buf = io.StringIO()
    # logging.basicConfig is idempotent enough for tests; install our buffer
    # as the only handler.
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(logging.StreamHandler(buf))
    root.setLevel(logging.INFO)

    configure_structlog(service)
    token = correlation_id_var.set("test-cid-xyz")
    try:
        structlog.get_logger().info("unit_test_event", user_id="u-1")
    finally:
        correlation_id_var.reset(token)

    line = buf.getvalue().strip().splitlines()[-1]
    return json.loads(line)


def test_log_line_includes_required_fields() -> None:
    record = _capture_log_line()
    assert record["correlation_id"] == "test-cid-xyz"
    assert record["service"] == "visibility"
    assert record["event"] == "unit_test_event"
    assert record["level"] == "info"
    assert record["user_id"] == "u-1"
    # ISO 8601 — structlog's TimeStamper(fmt="iso", utc=True) emits trailing Z.
    assert "T" in record["timestamp"]
    assert record["timestamp"].endswith("Z") or "+" in record["timestamp"]


# ----- counter increments on guardrail paths ----------------------------------


def _counter_value(metric, **labels) -> float:
    """Read a labeled counter sample. prometheus_client doesn't have a clean
    public getter, so we walk samples manually."""
    for m in metric.collect():
        for s in m.samples:
            if s.name.endswith("_total") and s.labels == labels:
                return s.value
    return 0.0


@pytest.mark.asyncio
async def test_cost_cap_short_circuit_increments_counters(session, monkeypatch) -> None:
    """Override decide() to return allowed=False and confirm the runner
    increments both the cost-cap and runs(status=cost_capped) counters
    before raising. Mirrors the request-shaped path: query exists, source
    is registered, the cost-cap gate fails."""
    from visibility import runner
    from visibility.costs import CapDecision, CostCapReached
    from visibility.models import Query

    q = Query(text="anything", category="generic", is_active=True)
    session.add(q)
    session.commit()
    session.refresh(q)

    monkeypatch.setattr(
        runner,
        "cost_decide",
        lambda *a, **kw: CapDecision(allowed=False, used_cents=999, cap_cents=1000, next_run_cents=20),
    )
    monkeypatch.setattr(runner, "alert_capped", lambda *a, **kw: None)

    before_cap = _counter_value(visibility_cost_cap_short_circuits_total, source="chatgpt")
    before_runs = _counter_value(visibility_runs_total, source="chatgpt", status="cost_capped")

    with pytest.raises(CostCapReached):
        await runner.run_query(session, q.id, "chatgpt")

    after_cap = _counter_value(visibility_cost_cap_short_circuits_total, source="chatgpt")
    after_runs = _counter_value(visibility_runs_total, source="chatgpt", status="cost_capped")
    assert after_cap == before_cap + 1
    assert after_runs == before_runs + 1


def test_cross_schema_link_failure_increments_counter(monkeypatch) -> None:
    """_warn_link_failure ticks the counter even when dedup suppresses the
    log line — cardinality is bounded by exception_class so the counter is a
    safer signal than parsing warning logs."""
    from visibility import tasks

    monkeypatch.setenv("VISIBILITY_DB_SCHEMA", "visibility")
    tasks._reset_link_warnings()

    before = _counter_value(
        visibility_cross_schema_link_failures_total,
        exception_class="RuntimeError",
    )
    tasks._warn_link_failure(RuntimeError("boom"), task_id=1, query_id=2)
    # second call: still increments the counter (per spec) even though the
    # warning log is deduped.
    tasks._warn_link_failure(RuntimeError("boom"), task_id=1, query_id=2)
    after = _counter_value(
        visibility_cross_schema_link_failures_total,
        exception_class="RuntimeError",
    )
    assert after == before + 2
