"""Per-(query, source) runner: cost-cap gate → fetch → idempotent persist →
detect mentions. Same-day double-runs no-op."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import anthropic
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from visibility.config import get_settings
from visibility.costs import CostCapReached, add as cost_add, alert_capped, decide as cost_decide
from visibility.detect import SentimentClassifier, detect_mentions, load_entities
from visibility.models import Entity, Mention, Query, Run
from visibility.sources import SourceResult, get_source

log = logging.getLogger(__name__)


class _AnthropicSentimentLLM:
    """Thin Claude wrapper used by SentimentClassifier on cache misses."""

    def __init__(self) -> None:
        s = get_settings()
        self._client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key)
        self._model = s.anthropic_model

    async def classify(self, prompt: str) -> str:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")


def _existing_run(session: Session, query_id: int, source: str, run_at: datetime) -> Run | None:
    return session.execute(
        select(Run).where(
            Run.query_id == query_id, Run.source == source, Run.run_date == run_at.date()
        )
    ).scalar_one_or_none()


async def run_query(
    session: Session,
    query_id: int,
    source: str,
    *,
    force: bool = False,
    classifier: SentimentClassifier | None = None,
) -> Run | None:
    """Returns the persisted Run, or None if skipped (already ran today / inactive)."""
    q: Query | None = session.get(Query, query_id)
    if q is None:
        raise ValueError(f"query {query_id} not found")
    if not q.is_active and not force:
        log.info("query %d inactive, skipping", query_id)
        return None

    run_at = datetime.now(timezone.utc)

    if not force:
        existing = _existing_run(session, query_id, source, run_at)
        if existing is not None:
            log.info("run for q=%d source=%s on %s already exists", query_id, source, run_at.date())
            return existing

    # Cost-cap gate BEFORE any destructive action. force=True does NOT bypass
    # cost protection — if we'd blow the cap, we raise and leave the existing
    # row intact.
    decision = cost_decide(session, source)
    if not decision.allowed:
        alert_capped(source, decision.used_cents, decision.cap_cents)
        raise CostCapReached(source, decision.used_cents, decision.cap_cents)

    # force=True: delete the existing same-day row (and its mentions, via
    # ON DELETE CASCADE on mentions.run_id) so the new row inserts cleanly
    # and the unique constraint stays satisfied. Done after the cost gate,
    # so a refused force never destroys data.
    if force:
        existing = _existing_run(session, query_id, source, run_at)
        if existing is not None:
            log.info("force=True: deleting existing run id=%d", existing.id)
            session.delete(existing)
            session.flush()

    source_fn = get_source(source)
    result: SourceResult = await source_fn(q.text)

    run = Run(
        query_id=q.id,
        source=source,
        run_at=run_at,
        run_date=run_at.date(),
        raw_response=result.raw_response,
        citations=list(result.citations or []),
        cost_cents=decision.next_run_cents,
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError:
        # Raced with a sibling worker — the partial-unique constraint won.
        session.rollback()
        return _existing_run(session, query_id, source, run_at)

    cost_add(session, source, decision.next_run_cents)
    await _detect_and_store(session, run, result, classifier)
    session.commit()
    return run


async def _detect_and_store(
    session: Session,
    run: Run,
    result: SourceResult,
    classifier: SentimentClassifier | None,
) -> None:
    entities = load_entities(session)
    if not entities:
        return
    if classifier is None:
        classifier = SentimentClassifier(session, _AnthropicSentimentLLM(), model_name=get_settings().anthropic_model)

    if result.serp_items:
        # Per-item detection so we can attribute SERP rank to each mention.
        name_by_id = {e.id: e.name for e in entities}
        for item in result.serp_items:
            text = f"{item.get('title','')}\n{item.get('snippet','')}\n{item.get('url','')}"
            mentions = await detect_mentions(text, entities, classifier)
            for m in mentions:
                session.add(
                    Mention(
                        run_id=run.id,
                        entity_id=m.entity_id,
                        position=m.position,
                        context=m.context,
                        sentiment=m.sentiment,
                        is_recommendation=m.is_recommendation,
                        rank=int(item.get("rank")) if item.get("rank") is not None else None,
                    )
                )
        _ = name_by_id  # silence linter
    else:
        mentions = await detect_mentions(result.raw_response, entities, classifier)
        for m in mentions:
            session.add(
                Mention(
                    run_id=run.id,
                    entity_id=m.entity_id,
                    position=m.position,
                    context=m.context,
                    sentiment=m.sentiment,
                    is_recommendation=m.is_recommendation,
                    rank=None,
                )
            )
