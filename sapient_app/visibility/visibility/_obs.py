"""Shared-observability bootstrap for the visibility service. See
app/_obs.py for the rationale — both Python services share
ops/logging/python/middleware.py via sys.path injection."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_OPS = Path(__file__).resolve().parents[2] / "ops" / "logging" / "python"
if str(_OPS) not in sys.path:
    sys.path.insert(0, str(_OPS))

if (env := os.environ.get("OPS_LOGGING_PATH")) and env not in sys.path:
    sys.path.insert(0, env)

from middleware import (  # noqa: E402
    CorrelationIdMiddleware,
    configure_structlog,
    correlation_id_var,
    get_logger,
)

__all__ = [
    "CorrelationIdMiddleware",
    "configure_structlog",
    "correlation_id_var",
    "get_logger",
]
