"""Shared-observability bootstrap for the visibility service. See
app/_obs.py for the rationale — both Python services share
ops/logging/python/middleware.py and behave identically on misconfig."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_env_override = os.environ.get("OPS_LOGGING_PATH")

if _env_override:
    # When set, the override is authoritative. We don't add the in-tree
    # relative path as a fallback — that would silently mask a bad config.
    _ops_path = _env_override
else:
    _ops_path = str(Path(__file__).resolve().parents[2] / "ops" / "logging" / "python")

if _ops_path not in sys.path:
    sys.path.insert(0, _ops_path)

try:
    from middleware import (  # noqa: E402
        CorrelationIdMiddleware,
        configure_structlog,
        correlation_id_var,
        get_logger,
    )
except ImportError as e:
    if _env_override:
        raise RuntimeError(
            f"OPS_LOGGING_PATH={_env_override!r} did not yield an importable "
            f"`middleware` module — fix the path or unset the variable to fall "
            f"back to stdlib logging."
        ) from e

    import contextvars
    import logging as _logging

    correlation_id_var = contextvars.ContextVar("correlation_id", default=None)

    class CorrelationIdMiddleware:  # type: ignore[no-redef]
        def __init__(self, app, **_kwargs) -> None:
            self.app = app

        async def __call__(self, scope, receive, send) -> None:
            await self.app(scope, receive, send)

    def configure_structlog(service_name: str, *, level: int = _logging.INFO) -> None:  # type: ignore[no-redef]
        _logging.basicConfig(level=level)

    def get_logger(name=None):  # type: ignore[no-redef]
        return _logging.getLogger(name)

__all__ = [
    "CorrelationIdMiddleware",
    "configure_structlog",
    "correlation_id_var",
    "get_logger",
]
