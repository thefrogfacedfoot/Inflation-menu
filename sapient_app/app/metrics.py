"""Prometheus metrics for the finder service. Sidecar served on
METRICS_PORT (default 9090). Defined alongside the existing app/ package so
poller.py can increment counters without circular imports."""
from __future__ import annotations

import os

from prometheus_client import Counter, start_http_server

finder_opportunities_scored_total = Counter(
    "finder_opportunities_scored_total",
    "Posts scored by the LLM, partitioned by whether they cleared the storage threshold",
    ["stored"],  # "true" | "false"
)


_started = False
_last_port = 0


def start_sidecar(default_port: int = 9090) -> int:
    global _started, _last_port
    if _started:
        return _last_port
    port = int(os.environ.get("METRICS_PORT", str(default_port)))
    start_http_server(port)
    _started = True
    _last_port = port
    return port
