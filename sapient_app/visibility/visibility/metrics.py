"""Prometheus counters and histograms for the visibility service.

Served from a sidecar HTTP server on port METRICS_PORT (default 9092). The
main FastAPI app does NOT mount /metrics — keeping scrape traffic off the
user-facing port is a small but real isolation win.
"""
from __future__ import annotations

import os

from prometheus_client import Counter, Histogram, start_http_server

# ---- counters ----------------------------------------------------------------

visibility_runs_total = Counter(
    "visibility_runs_total",
    "Source runs completed, partitioned by terminal status",
    ["source", "status"],  # status ∈ {success, upstream_error, cost_capped}
)

visibility_cost_cap_short_circuits_total = Counter(
    "visibility_cost_cap_short_circuits_total",
    "Times a runner refused to spend because the per-source per-day cap was hit",
    ["source"],
)

visibility_cross_schema_link_failures_total = Counter(
    "visibility_cross_schema_link_failures_total",
    "Failed lookups against public.opportunities from gap-task generation",
    ["exception_class"],
)

# ---- histograms --------------------------------------------------------------

visibility_source_latency_seconds = Histogram(
    "visibility_source_latency_seconds",
    "Wall time of a single upstream source.query() call",
    ["source"],
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)


def start_sidecar(default_port: int = 9092) -> int:
    """Start the prometheus_client WSGI server on the metrics sidecar port.
    Returns the port actually used. Idempotent on the process; subsequent
    calls are no-ops (prometheus_client's start_http_server doesn't track
    starts, so we guard here)."""
    global _started
    if _started:
        return _last_port
    port = int(os.environ.get("METRICS_PORT", str(default_port)))
    start_http_server(port)
    _started = True
    _last_port = port
    return port


_started = False
_last_port = 0
