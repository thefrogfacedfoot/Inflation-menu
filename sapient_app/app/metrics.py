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

# Bounded label set — see app.scorer.classify_scoring_error. A scored-but-
# rejected post (low relevance) ticks opportunities_scored_total{stored=false},
# NOT this counter; the two are mutually exclusive by design so the rate of
# this metric maps cleanly to "model/upstream unhealthy."
finder_scoring_errors_total = Counter(
    "finder_scoring_errors_total",
    "Scoring attempts that raised, partitioned by classified reason",
    ["reason"],  # rate_limited | timeout | upstream_5xx | json_parse | schema_invalid | other
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
