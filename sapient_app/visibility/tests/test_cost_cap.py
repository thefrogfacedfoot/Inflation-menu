from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from visibility.config import get_settings
from visibility.costs import CostCapReached, add, alert_capped, decide, used_cents_today
from visibility.models import DailyCost


def test_decide_allows_when_under_cap(session):
    s = get_settings()
    s.cost_cap_chatgpt = 100
    s.cost_per_run_chatgpt = 5

    d = decide(session, "chatgpt", settings=s, today=date(2026, 6, 20))
    assert d.allowed is True
    assert d.used_cents == 0
    assert d.next_run_cents == 5


def test_decide_refuses_when_next_run_would_exceed_cap(session):
    s = get_settings()
    s.cost_cap_chatgpt = 100
    s.cost_per_run_chatgpt = 5
    session.add(DailyCost(source="chatgpt", day=date(2026, 6, 20), cents_used=98, runs_count=20))
    session.commit()

    d = decide(session, "chatgpt", settings=s, today=date(2026, 6, 20))
    assert d.allowed is False
    assert d.used_cents == 98


def test_decide_zero_cap_means_unlimited(session):
    s = get_settings()
    s.cost_cap_reddit_search = 0
    s.cost_per_run_reddit_search = 0
    session.add(DailyCost(source="reddit_search", day=date(2026, 6, 20), cents_used=10_000, runs_count=999))
    session.commit()

    d = decide(session, "reddit_search", settings=s, today=date(2026, 6, 20))
    assert d.allowed is True


def test_add_accumulates_per_day(session):
    add(session, "chatgpt", 5, today=date(2026, 6, 20))
    add(session, "chatgpt", 5, today=date(2026, 6, 20))
    add(session, "chatgpt", 5, today=date(2026, 6, 21))
    session.commit()
    assert used_cents_today(session, "chatgpt", today=date(2026, 6, 20)) == 10
    assert used_cents_today(session, "chatgpt", today=date(2026, 6, 21)) == 5


@pytest.mark.asyncio
async def test_runner_short_circuits_at_cap_and_creates_no_run(session, monkeypatch):
    """End-to-end: with the cap already hit, run_query raises and writes nothing."""
    from visibility.models import Query
    from visibility import runner

    s = get_settings()
    s.cost_cap_chatgpt = 50
    s.cost_per_run_chatgpt = 100  # one run would blow past the cap

    q = Query(text="best widget for x", category="general")
    session.add(q)
    session.commit()

    # The source function MUST NOT be called when the cap blocks.
    called = {"n": 0}

    async def _should_not_be_called(_q):
        called["n"] += 1
        raise AssertionError("source called even though cost cap should have blocked")

    monkeypatch.setattr(runner, "get_source", lambda name: _should_not_be_called)

    fired: list[tuple[str, int, int]] = []

    def _fake_alert(src, used, cap):
        fired.append((src, used, cap))

    monkeypatch.setattr(runner, "alert_capped", _fake_alert)

    with pytest.raises(CostCapReached):
        await runner.run_query(session, q.id, "chatgpt")

    assert called["n"] == 0
    assert fired and fired[0][0] == "chatgpt"
    # No run row written.
    from sqlalchemy import select

    from visibility.models import Run

    assert session.execute(select(Run)).first() is None


def test_alert_capped_no_webhook_is_silent(monkeypatch):
    monkeypatch.setenv("COST_CAP_WEBHOOK_URL", "")
    # Just doesn't raise.
    alert_capped("chatgpt", 100, 100)
