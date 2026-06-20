"""Cross-schema opportunity-link failures: warn once per process, silent in
SQLite mode. Setup builds the minimum data shape that makes the gap-task
generator produce a task (so the link lookup actually fires)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest

from visibility import tasks as tasks_module
from visibility.models import Entity, Mention, Query, Run


def _seed_gap_world(session) -> tuple[int, int]:
    """Build the minimum data shape that makes generate_gap_tasks produce
    one reddit_top_voted_answer task. Returns (query_id, brand_id)."""
    q = Query(text="best widget for x")
    brand = Entity(name="Acme", type="brand", aliases=[])
    session.add_all([q, brand])
    session.commit()

    now = datetime.now(timezone.utc) - timedelta(days=1)
    # An LLM run with no Acme mention.
    llm_run = Run(
        query_id=q.id,
        source="chatgpt",
        run_at=now,
        run_date=now.date(),
        raw_response="competitor analysis without the brand",
        citations=[],
    )
    # A SERP run with a Reddit URL in the top results.
    serp_run = Run(
        query_id=q.id,
        source="serp",
        run_at=now,
        run_date=now.date(),
        raw_response="ranked results",
        citations=[
            "https://www.reddit.com/r/widgets/comments/abc123/best_widget_for_x",
        ],
    )
    session.add_all([llm_run, serp_run])
    session.commit()
    return q.id, brand.id


def test_no_schema_means_no_warning(session, monkeypatch, caplog):
    monkeypatch.setenv("VISIBILITY_DB_SCHEMA", "")
    tasks_module._reset_link_warnings()

    def _always_raises(_session, _url):
        raise RuntimeError("simulated cross-schema failure")

    monkeypatch.setattr(tasks_module, "_resolve_finder_opportunity", _always_raises)
    _seed_gap_world(session)

    with caplog.at_level(logging.WARNING, logger="visibility.tasks"):
        tasks_module.generate_gap_tasks(session)
        tasks_module.generate_gap_tasks(session)

    assert [r for r in caplog.records if "cross-schema" in r.getMessage()] == []


def test_with_schema_warns_exactly_once_across_two_generate_calls(session, monkeypatch, caplog):
    monkeypatch.setenv("VISIBILITY_DB_SCHEMA", "visibility")
    tasks_module._reset_link_warnings()

    def _always_raises(_session, _url):
        raise RuntimeError("simulated cross-schema failure")

    monkeypatch.setattr(tasks_module, "_resolve_finder_opportunity", _always_raises)
    _seed_gap_world(session)

    with caplog.at_level(logging.WARNING, logger="visibility.tasks"):
        tasks_module.generate_gap_tasks(session)
        # Second pass: existing task is deduped, link lookup wouldn't fire
        # again here, but the dedup invariant must hold even if it did.
        tasks_module.generate_gap_tasks(session)

    warnings = [r for r in caplog.records if "cross-schema" in r.getMessage()]
    assert len(warnings) == 1
    msg = warnings[0].getMessage()
    assert "RuntimeError" in msg
    assert "query_id=" in msg
    assert "task_id=" in msg


def test_dedup_holds_across_multiple_link_attempts_in_one_pass(session, monkeypatch, caplog):
    """If generate_gap_tasks creates N tasks in one pass and each link lookup
    raises, we still warn exactly once."""
    monkeypatch.setenv("VISIBILITY_DB_SCHEMA", "visibility")
    tasks_module._reset_link_warnings()

    calls = {"n": 0}

    def _always_raises(_session, _url):
        calls["n"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(tasks_module, "_resolve_finder_opportunity", _always_raises)

    # Drive _upsert_task directly with N different URLs in one logical pass.
    q = Query(text="q1")
    brand = Entity(name="Acme", type="brand", aliases=[])
    session.add_all([q, brand])
    session.commit()

    with caplog.at_level(logging.WARNING, logger="visibility.tasks"):
        for i in range(3):
            tasks_module._upsert_task(
                session,
                kind="reddit_top_voted_answer",
                query_id=q.id,
                entity_id=brand.id,
                related_url=f"https://reddit.com/r/x/comments/abc{i}",
                recommendation=f"rec {i}",
            )

    assert calls["n"] == 3, "every task should have attempted a link lookup"
    warnings = [r for r in caplog.records if "cross-schema" in r.getMessage()]
    assert len(warnings) == 1


def test_dedup_key_includes_schema(session, monkeypatch, caplog):
    """Same exception class but a different schema → a second warning fires."""
    tasks_module._reset_link_warnings()

    def _always_raises(_session, _url):
        raise RuntimeError("boom")

    monkeypatch.setattr(tasks_module, "_resolve_finder_opportunity", _always_raises)

    q = Query(text="q1")
    brand = Entity(name="Acme", type="brand", aliases=[])
    session.add_all([q, brand])
    session.commit()

    with caplog.at_level(logging.WARNING, logger="visibility.tasks"):
        monkeypatch.setenv("VISIBILITY_DB_SCHEMA", "schema_a")
        tasks_module._upsert_task(
            session,
            kind="reddit_top_voted_answer",
            query_id=q.id,
            entity_id=brand.id,
            related_url="https://reddit.com/r/x/comments/abc",
            recommendation="r",
        )
        monkeypatch.setenv("VISIBILITY_DB_SCHEMA", "schema_b")
        tasks_module._upsert_task(
            session,
            kind="reddit_top_voted_answer",
            query_id=q.id,
            entity_id=brand.id,
            related_url="https://reddit.com/r/x/comments/xyz",
            recommendation="r2",
        )

    warnings = [r for r in caplog.records if "cross-schema" in r.getMessage()]
    assert len(warnings) == 2
