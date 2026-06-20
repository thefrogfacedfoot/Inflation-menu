"""Shared-observability bootstrap. Resolves and imports the cross-service
correlation-id middleware and structlog config from `ops/logging/python/`.

The shared file lives outside the `app` package on purpose — see the
top-level spec — so we prepend its directory to sys.path here, then
re-export the public surface. Callers do:

    from app._obs import CorrelationIdMiddleware, configure_structlog, get_logger

Path resolution:
  - If `OPS_LOGGING_PATH` is set, IT is the authoritative path. Anything else
    is silently ignored so a misconfigured override actually surfaces.
  - If unset, we use the in-tree relative path (one level above this file).

Failure modes:
  - OPS_LOGGING_PATH set + import fails → RuntimeError naming the attempted
    path with the original exception chained. The operator pointed
    deployment at the wrong directory; that needs to be loud.
  - OPS_LOGGING_PATH unset + import fails → silent stdlib fallback.
    Running the service in a local venv without the ops/ tree mounted is a
    legitimate dev workflow; correlation ids and JSON output are nice-to-have
    there, not required.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_env_override = os.environ.get("OPS_LOGGING_PATH")

if _env_override:
    # Authoritative — don't paper over a bad override by also trying the
    # in-tree path.
    _ops_path = _env_override
else:
    _ops_path = str(Path(__file__).resolve().parents[1] / "ops" / "logging" / "python")

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

    # Silent stdlib fallback. Mirrors the surface of middleware.py but
    # without correlation-id propagation or JSON output.
    import contextvars
    import logging as _logging

    correlation_id_var = contextvars.ContextVar("correlation_id", default=None)

    class CorrelationIdMiddleware:  # type: ignore[no-redef]
        """No-op pass-through. Real implementation lives in ops/logging/python/."""

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
