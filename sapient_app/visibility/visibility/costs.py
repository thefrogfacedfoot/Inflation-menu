"""Per-source per-day cost cap. The runner consults `would_exceed` before
spending money, and calls `add` after a successful run."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from visibility.config import Settings, get_settings
from visibility.models import DailyCost

log = logging.getLogger(__name__)


class CostCapReached(Exception):
    def __init__(self, source: str, used_cents: int, cap_cents: int):
        super().__init__(
            f"cost cap reached for {source}: used {used_cents}c, cap {cap_cents}c"
        )
        self.source = source
        self.used_cents = used_cents
        self.cap_cents = cap_cents


@dataclass(frozen=True)
class CapDecision:
    allowed: bool
    used_cents: int
    cap_cents: int
    next_run_cents: int


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _row(session: Session, source: str, day: date) -> DailyCost | None:
    return session.execute(
        select(DailyCost).where(DailyCost.source == source, DailyCost.day == day)
    ).scalar_one_or_none()


def used_cents_today(session: Session, source: str, *, today: date | None = None) -> int:
    row = _row(session, source, today or _today())
    return row.cents_used if row else 0


def decide(
    session: Session,
    source: str,
    *,
    settings: Settings | None = None,
    today: date | None = None,
) -> CapDecision:
    s = settings or get_settings()
    cap = s.cap_cents(source)
    per_run = s.per_run_cents(source)
    used = used_cents_today(session, source, today=today)
    if cap <= 0:
        return CapDecision(allowed=True, used_cents=used, cap_cents=cap, next_run_cents=per_run)
    allowed = used + per_run <= cap
    return CapDecision(allowed=allowed, used_cents=used, cap_cents=cap, next_run_cents=per_run)


def add(session: Session, source: str, cents: int, *, today: date | None = None) -> None:
    day = today or _today()
    # Flush pending inserts so the SELECT below sees rows from a previous add()
    # in this same transaction; without it, a second add() in the same session
    # would insert a duplicate and trip the (source, day) unique constraint.
    session.flush()
    row = _row(session, source, day)
    if row is None:
        session.add(DailyCost(source=source, day=day, cents_used=cents, runs_count=1))
    else:
        row.cents_used += cents
        row.runs_count += 1


def alert_capped(source: str, used: int, cap: int) -> None:
    url = get_settings().cost_cap_webhook_url
    if not url:
        log.warning("cost cap hit for %s (used=%d cap=%d) — no webhook configured", source, used, cap)
        return
    try:
        httpx.post(
            url,
            json={
                "event": "cost_cap_reached",
                "source": source,
                "used_cents": used,
                "cap_cents": cap,
            },
            timeout=5.0,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("cost cap webhook failed: %s", e)
