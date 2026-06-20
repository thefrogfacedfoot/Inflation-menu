"""Shared-observability bootstrap. Resolves and imports the cross-service
correlation-id middleware and structlog config from `ops/logging/python/`.

The shared file lives outside the `app` package on purpose — see the
top-level spec — so we prepend its directory to sys.path here, then
re-export the public surface. Callers do:

    from app._obs import CorrelationIdMiddleware, configure_structlog, get_logger
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_OPS = Path(__file__).resolve().parents[1] / "ops" / "logging" / "python"
if str(_OPS) not in sys.path:
    sys.path.insert(0, str(_OPS))

# Also respect an explicit override (e.g. set in docker-compose).
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
