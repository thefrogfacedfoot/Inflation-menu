"""APScheduler wiring — three source cadences plus a daily gap-task pass."""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from visibility.config import get_settings
from visibility.db import session_scope
from visibility.models import Query
from visibility.runner import run_query
from visibility.tasks import generate_gap_tasks

log = logging.getLogger(__name__)


async def _fan_out(source: str) -> None:
    with session_scope() as session:
        query_ids = list(
            session.execute(select(Query.id).where(Query.is_active.is_(True))).scalars()
        )
    for qid in query_ids:
        try:
            with session_scope() as session:
                await run_query(session, qid, source)
        except Exception as e:  # noqa: BLE001
            log.warning("run_query failed for q=%d source=%s: %s", qid, source, e)


async def _generate_tasks() -> None:
    with session_scope() as session:
        created = generate_gap_tasks(session)
        log.info("generated %d gap tasks", len(created))


def build_scheduler() -> AsyncIOScheduler:
    s = get_settings()
    sched = AsyncIOScheduler(timezone="UTC")

    # LLM sources — daily by default.
    for source in ("chatgpt", "claude", "gemini", "perplexity"):
        sched.add_job(
            _fan_out,
            IntervalTrigger(hours=s.schedule_llm_hours),
            args=[source],
            id=f"fanout-{source}",
            replace_existing=True,
            misfire_grace_time=3600,
        )

    sched.add_job(
        _fan_out,
        IntervalTrigger(hours=s.schedule_serp_hours),
        args=["serp"],
        id="fanout-serp",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    sched.add_job(
        _fan_out,
        IntervalTrigger(hours=s.schedule_reddit_hours),
        args=["reddit_search"],
        id="fanout-reddit",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    sched.add_job(
        _generate_tasks,
        IntervalTrigger(hours=s.schedule_tasks_hours),
        id="gap-tasks",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    return sched
