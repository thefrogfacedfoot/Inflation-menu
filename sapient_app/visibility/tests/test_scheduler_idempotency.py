"""The scheduler's idempotency guarantee — same (query, source, day) doesn't
double-run — lives in runner.run_query. We exercise it via the runner."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from visibility import runner
from visibility.config import get_settings
from visibility.costs import CostCapReached
from visibility.detect import SentimentClassifier, SentimentResult
from visibility.models import DailyCost, Entity, Mention, Query, Run
from visibility.sources.base import SourceResult


class _NoopClassifier(SentimentClassifier):
    def __init__(self):  # bypass parent init — we won't touch the DB
        pass

    async def classify(self, context, entity_id, entity_name):
        return SentimentResult("neutral", False)


def _stub_source_factory(text: str):
    """Returns (source_fn, call_count) where source_fn yields a SourceResult
    with `text` and counter advances on each call."""
    state = {"calls": 0}

    async def _q(_q: str) -> SourceResult:
        state["calls"] += 1
        return SourceResult(
            raw_response=f"{text} #{state['calls']}",
            citations=[],
            fetched_at=datetime.now(timezone.utc),
        )

    return _q, state


@pytest.mark.asyncio
async def test_same_day_double_run_creates_one_row(session, monkeypatch):
    s = get_settings()
    s.cost_cap_chatgpt = 10_000
    s.cost_per_run_chatgpt = 5

    q = Query(text="best widget for x")
    e = Entity(name="Acme", type="brand", aliases=[])
    session.add_all([q, e])
    session.commit()

    source_fn, calls = _stub_source_factory("Acme is great")
    monkeypatch.setattr(runner, "get_source", lambda name: source_fn)

    classifier = _NoopClassifier()
    r1 = await runner.run_query(session, q.id, "chatgpt", classifier=classifier)
    r2 = await runner.run_query(session, q.id, "chatgpt", classifier=classifier)

    assert r1 is not None and r2 is not None
    assert r1.id == r2.id
    # Second call must NOT have hit the upstream source.
    assert calls["calls"] == 1
    assert len(list(session.execute(select(Run)).scalars())) == 1


@pytest.mark.asyncio
async def test_force_true_deletes_and_replaces_run_and_mentions(session, monkeypatch):
    s = get_settings()
    s.cost_cap_chatgpt = 10_000
    s.cost_per_run_chatgpt = 5

    q = Query(text="best widget for x")
    acme = Entity(name="Acme", type="brand", aliases=[])
    beta = Entity(name="Beta", type="competitor", aliases=[])
    session.add_all([q, acme, beta])
    session.commit()

    # First call: response mentions Acme.
    call_log: list[str] = []

    async def _first_response(_q: str) -> SourceResult:
        call_log.append("first")
        return SourceResult(
            raw_response="Acme is great",
            citations=[],
            fetched_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(runner, "get_source", lambda name: _first_response)
    classifier = _NoopClassifier()
    r1 = await runner.run_query(session, q.id, "chatgpt", classifier=classifier)
    assert r1 is not None
    old_run_id = r1.id
    old_mentions = list(session.execute(select(Mention).where(Mention.run_id == old_run_id)).scalars())
    assert len(old_mentions) == 1
    assert old_mentions[0].entity_id == acme.id

    # Force-rerun. Different response, mentions Beta instead.
    async def _second_response(_q: str) -> SourceResult:
        call_log.append("second")
        return SourceResult(
            raw_response="Beta is great",
            citations=[],
            fetched_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(runner, "get_source", lambda name: _second_response)
    r2 = await runner.run_query(session, q.id, "chatgpt", force=True, classifier=classifier)

    assert r2 is not None
    assert r2.id != old_run_id, "force=True must produce a NEW run, not return the existing one"
    assert call_log == ["first", "second"], "upstream should have been called twice"

    # Exactly one Run row remains for today.
    rows = list(session.execute(select(Run)).scalars())
    assert len(rows) == 1
    assert rows[0].id == r2.id

    # Old mentions gone via CASCADE; new ones reflect the new response.
    gone = session.execute(select(Mention).where(Mention.run_id == old_run_id)).first()
    assert gone is None
    new_mentions = list(session.execute(select(Mention).where(Mention.run_id == r2.id)).scalars())
    assert len(new_mentions) == 1
    assert new_mentions[0].entity_id == beta.id


@pytest.mark.asyncio
async def test_force_true_does_not_bypass_cost_cap(session, monkeypatch):
    """force=True past the cap → CostCapReached. No DELETE happens. The
    existing row stays intact (verify by id)."""
    s = get_settings()
    s.cost_cap_chatgpt = 10_000
    s.cost_per_run_chatgpt = 5

    q = Query(text="best widget for x")
    session.add(q)
    session.commit()

    # First, populate a Run for today within the budget.
    async def _ok_source(_q: str) -> SourceResult:
        return SourceResult("first", [], datetime.now(timezone.utc))

    monkeypatch.setattr(runner, "get_source", lambda name: _ok_source)
    r1 = await runner.run_query(session, q.id, "chatgpt", classifier=_NoopClassifier())
    assert r1 is not None
    original_id = r1.id

    # Now tighten the cap so the next run would exceed it.
    s.cost_cap_chatgpt = 5  # already used 5; next 5-cent run would exceed
    s.cost_per_run_chatgpt = 5

    async def _should_not_be_called(_q: str) -> SourceResult:
        raise AssertionError("upstream called even though cost cap should have blocked")

    monkeypatch.setattr(runner, "get_source", lambda name: _should_not_be_called)
    monkeypatch.setattr(runner, "alert_capped", lambda *a, **kw: None)

    with pytest.raises(CostCapReached):
        await runner.run_query(session, q.id, "chatgpt", force=True, classifier=_NoopClassifier())

    # The existing row is intact — DELETE never ran.
    rows = list(session.execute(select(Run)).scalars())
    assert len(rows) == 1
    assert rows[0].id == original_id


@pytest.mark.asyncio
async def test_force_false_with_existing_returns_existing_no_upstream(session, monkeypatch):
    s = get_settings()
    s.cost_cap_chatgpt = 10_000
    s.cost_per_run_chatgpt = 5

    q = Query(text="best widget for x")
    session.add(q)
    session.commit()

    source_fn, calls = _stub_source_factory("hello")
    monkeypatch.setattr(runner, "get_source", lambda name: source_fn)

    r1 = await runner.run_query(session, q.id, "chatgpt", classifier=_NoopClassifier())
    assert r1 is not None
    assert calls["calls"] == 1

    r2 = await runner.run_query(session, q.id, "chatgpt", classifier=_NoopClassifier())
    assert r2 is not None
    assert r2.id == r1.id
    assert calls["calls"] == 1, "force=False with existing run must skip the upstream call"


@pytest.mark.asyncio
async def test_different_sources_same_day_create_separate_runs(session, monkeypatch):
    s = get_settings()
    for src in ("chatgpt", "claude"):
        setattr(s, f"cost_cap_{src}", 10_000)
        setattr(s, f"cost_per_run_{src}", 5)

    q = Query(text="best widget for x")
    session.add(q)
    session.commit()

    async def _src(name: str):
        async def _q(_q: str) -> SourceResult:
            return SourceResult(f"source={name}", [], datetime.now(timezone.utc))

        return _q

    monkeypatch.setattr(
        runner,
        "get_source",
        lambda name: (
            _src("chatgpt") if name == "chatgpt" else _src("claude")
        ).__wrapped__ if False else _stub_source_factory(f"source={name}")[0],
    )

    classifier = _NoopClassifier()
    await runner.run_query(session, q.id, "chatgpt", classifier=classifier)
    await runner.run_query(session, q.id, "claude", classifier=classifier)

    rows = list(session.execute(select(Run)).scalars())
    assert len(rows) == 2
    assert {r.source for r in rows} == {"chatgpt", "claude"}
