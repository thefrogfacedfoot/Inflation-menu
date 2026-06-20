"""Gap-analysis task generator. Two patterns:

  1. reddit_top_voted_answer — brand isn't mentioned in any LLM run for query Q
     in the last LLM_WINDOW_DAYS, BUT a Reddit thread ranks top-N for Q on
     Google. Suggest: get a top-voted answer there.

  2. reddit_no_brand_reply — competitor is mentioned in >=80% of LLM runs
     for query Q in the window, AND a Reddit-search run for Q surfaced a thread
     with no brand mention. Suggest: draft a reply via the dashboard's
     tone-adapter.

Tasks dedupe by (kind, query_id, entity_id, related_url) — re-running the
generator on the same data is a no-op.
"""
from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import and_, select, text
from sqlalchemy.orm import Session

from visibility.db import SCHEMA
from visibility.models import Entity, Mention, Query, Run, Task

log = logging.getLogger(__name__)

LLM_SOURCES = ("chatgpt", "claude", "gemini", "perplexity")
WINDOW_DAYS = 14
SERP_REDDIT_TOP_N = 3
COMPETITOR_DOMINANCE = 0.8

# Per-process dedup for cross-schema opportunity-link warnings, keyed by
# (exception_class_name, schema). Set so we warn once per process per
# (failure mode, schema), not once per gap-task pass.
_LINK_WARNED: set[tuple[str, str]] = set()


def _reset_link_warnings() -> None:
    """Test helper — clears the warning dedup state."""
    _LINK_WARNED.clear()


def _warn_link_failure(exc: BaseException, *, task_id: Optional[int], query_id: int) -> None:
    """Log a single warning per (exception_class, schema) per process.

    SQLite/empty-schema mode is silent: the cross-schema query can never
    succeed there, and tests would drown in noise otherwise.
    """
    schema = os.getenv("VISIBILITY_DB_SCHEMA", "")
    if not schema:
        return
    key = (type(exc).__name__, schema)
    if key in _LINK_WARNED:
        return
    _LINK_WARNED.add(key)
    log.warning(
        "cross-schema opportunity link failed "
        "(task_id=%s query_id=%s exc=%s schema=%s): %s",
        task_id, query_id, type(exc).__name__, schema, exc,
    )


def _is_reddit_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:  # noqa: BLE001
        return False
    return host.endswith("reddit.com")


_SUBREDDIT_RE = re.compile(r"/r/([A-Za-z0-9_]+)(?:/|$)")


def _subreddit_from_url(url: str) -> Optional[str]:
    """Extract subreddit name from a Reddit URL. Returns None if not Reddit
    or no /r/<name>/ segment present."""
    if not _is_reddit_url(url):
        return None
    m = _SUBREDDIT_RE.search(url)
    return m.group(1) if m else None


def _resolve_finder_opportunity(session: Session, url: str) -> Optional[int]:
    """Cross-schema lookup against public.opportunities. RAISES on DB errors
    (no silent catch); the caller wraps this in a savepoint and routes
    failures through _warn_link_failure so dedup state lives in one place."""
    if not url:
        return None
    row = session.execute(
        text("SELECT id FROM public.opportunities WHERE post_url = :u LIMIT 1"),
        {"u": url},
    ).first()
    return int(row[0]) if row else None


def _upsert_task(
    session: Session,
    *,
    kind: str,
    query_id: int,
    entity_id: Optional[int],
    related_url: Optional[str],
    recommendation: str,
    suggested_subreddit: Optional[str] = None,
) -> Optional[Task]:
    existing = session.execute(
        select(Task).where(
            Task.kind == kind,
            Task.query_id == query_id,
            Task.entity_id == entity_id,
            Task.related_url == related_url,
            Task.status == "open",
        )
    ).scalar_one_or_none()
    if existing:
        return None

    task = Task(
        kind=kind,
        query_id=query_id,
        entity_id=entity_id,
        related_url=related_url,
        recommendation=recommendation,
        suggested_subreddit=suggested_subreddit,
    )
    session.add(task)
    # Flush so task.id is available for the warning, and so the savepoint
    # below isolates only the cross-schema lookup.
    session.flush()

    if related_url:
        finder_id: Optional[int] = None
        try:
            with session.begin_nested():
                finder_id = _resolve_finder_opportunity(session, related_url)
        except Exception as e:  # noqa: BLE001
            _warn_link_failure(e, task_id=task.id, query_id=query_id)
            finder_id = None
        if finder_id is not None:
            task.finder_opportunity_id = finder_id
    return task


def generate_gap_tasks(session: Session, *, now: datetime | None = None) -> list[Task]:
    """Returns the new tasks created in this pass."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=WINDOW_DAYS)

    brands = list(
        session.execute(select(Entity).where(Entity.type == "brand")).scalars()
    )
    competitors = list(
        session.execute(select(Entity).where(Entity.type == "competitor")).scalars()
    )
    queries = list(
        session.execute(select(Query).where(Query.is_active.is_(True))).scalars()
    )

    created: list[Task] = []
    for q in queries:
        llm_runs = list(
            session.execute(
                select(Run).where(
                    Run.query_id == q.id, Run.source.in_(LLM_SOURCES), Run.run_at >= since
                )
            ).scalars()
        )
        if not llm_runs:
            continue
        llm_run_ids = [r.id for r in llm_runs]

        mentions = list(
            session.execute(
                select(Mention).where(Mention.run_id.in_(llm_run_ids))
            ).scalars()
        )
        mention_runs_by_entity: dict[int, set[int]] = defaultdict(set)
        for m in mentions:
            mention_runs_by_entity[m.entity_id].add(m.run_id)

        # Gap 1: brand absent in LLM, Reddit thread top-3 on SERP for same query.
        for brand in brands:
            if mention_runs_by_entity.get(brand.id):
                continue
            serp_run = session.execute(
                select(Run)
                .where(Run.query_id == q.id, Run.source == "serp", Run.run_at >= since)
                .order_by(Run.run_at.desc())
            ).scalars().first()
            if not serp_run:
                continue
            reddit_urls = [
                u for u in (serp_run.citations or [])[:SERP_REDDIT_TOP_N] if _is_reddit_url(u)
            ]
            for url in reddit_urls:
                rec = (
                    f"Brand '{brand.name}' is absent in LLM responses for "
                    f"query '{q.text}', but Reddit thread {url} ranks in the top "
                    f"{SERP_REDDIT_TOP_N} on Google for it. Get a top-voted answer there."
                )
                t = _upsert_task(
                    session,
                    kind="reddit_top_voted_answer",
                    query_id=q.id,
                    entity_id=brand.id,
                    related_url=url,
                    recommendation=rec,
                    suggested_subreddit=_subreddit_from_url(url),
                )
                if t:
                    created.append(t)

        # Gap 2: competitor dominates LLM, Reddit thread for same query lacks brand.
        total_llm_runs = len(llm_run_ids)
        brand_run_ids: set[int] = set()
        for brand in brands:
            brand_run_ids |= mention_runs_by_entity.get(brand.id, set())

        for comp in competitors:
            dom = len(mention_runs_by_entity.get(comp.id, set())) / max(1, total_llm_runs)
            if dom < COMPETITOR_DOMINANCE:
                continue
            reddit_run = session.execute(
                select(Run)
                .where(Run.query_id == q.id, Run.source == "reddit_search", Run.run_at >= since)
                .order_by(Run.run_at.desc())
            ).scalars().first()
            if not reddit_run:
                continue
            # Pick the first Reddit thread whose mentions don't include any brand.
            brand_ids = {b.id for b in brands}
            thread_urls = list(reddit_run.citations or [])
            reddit_run_mentions = [m for m in mentions if m.run_id == reddit_run.id]
            brand_mentioned = any(m.entity_id in brand_ids for m in reddit_run_mentions)
            if brand_mentioned or not thread_urls:
                continue
            url = thread_urls[0]
            rec = (
                f"Competitor '{comp.name}' is mentioned in {dom:.0%} of LLM responses for "
                f"query '{q.text}'; Reddit thread {url} has no brand mention. "
                f"Draft a reply via the dashboard's tone-adapter."
            )
            t = _upsert_task(
                session,
                kind="reddit_no_brand_reply",
                query_id=q.id,
                entity_id=comp.id,
                related_url=url,
                recommendation=rec,
                suggested_subreddit=_subreddit_from_url(url),
            )
            if t:
                created.append(t)

    session.flush()
    return created
