"""Shared FastAPI / Starlette structured-logging plumbing.

Used by finder and visibility. Adds:
  - correlation_id_var: ContextVar carried implicitly across awaits.
  - CorrelationIdMiddleware: reads X-Correlation-Id (generates a UUID4 if
    absent), stores it in the contextvar, echoes it on the response.
  - configure_structlog(service_name): JSON renderer with the required
    fields on every line.
"""
from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Awaitable, Callable, Optional

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Carried implicitly across awaits via contextvars. Other modules can import
# this and call .get() / .set() directly when they need to attach an id to
# work that didn't originate from an HTTP request (background jobs, CLI).
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


class CorrelationIdMiddleware:
    """Pure ASGI middleware. Lighter than BaseHTTPMiddleware (no extra task)
    and works with WebSockets gracefully."""

    HEADER = "x-correlation-id"

    def __init__(self, app: ASGIApp, *, header: str = HEADER) -> None:
        self.app = app
        self.header = header.lower().encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        cid = _extract_header(scope, self.header) or str(uuid.uuid4())
        token = correlation_id_var.set(cid)

        async def _send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((self.header, cid.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, _send_with_header)
        finally:
            correlation_id_var.reset(token)


def _extract_header(scope: Scope, name: bytes) -> Optional[str]:
    for k, v in scope.get("headers") or []:
        if k.lower() == name:
            return v.decode()
    return None


# ---- structlog processors ----------------------------------------------------


def _add_correlation_id(_, __, event_dict):
    cid = correlation_id_var.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def _add_service(service_name: str):
    def _proc(_, __, event_dict):
        event_dict["service"] = service_name
        return event_dict

    return _proc


def _rename_message_to_event(_, __, event_dict):
    # structlog uses "event" for the message; spec calls for "event" snake_case
    # verb. Nothing to translate — kept as a hook for downstream conventions.
    return event_dict


def configure_structlog(service_name: str, *, level: int = logging.INFO) -> None:
    """Idempotent — safe to call from each service's init or from tests."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_correlation_id,
            _add_service(service_name),
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            _rename_message_to_event,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None):
    """Convenience accessor — keeps callers from importing structlog directly."""
    return structlog.get_logger(name) if name else structlog.get_logger()
