from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select

from app.config import Settings, get_settings
from app.db import session_scope
from app.metrics import finder_opportunities_scored_total
from app.models import Opportunity
from app.reddit_client import RedditClient, RedditPost
from app.scorer import Scorer

log = logging.getLogger(__name__)


@dataclass
class CycleStats:
    fetched: int = 0
    keyword_hits: int = 0
    scored: int = 0
    stored: int = 0
    skipped_duplicate: int = 0


def _matches_keywords(post: RedditPost, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{post.title}\n{post.body}".lower()
    return any(k.lower() in haystack for k in keywords)


def _existing_post_ids(post_ids: list[str]) -> set[str]:
    if not post_ids:
        return set()
    with session_scope() as session:
        rows = session.execute(
            select(Opportunity.post_id).where(Opportunity.post_id.in_(post_ids))
        ).all()
    return {r[0] for r in rows}


def _resolve_subreddits(reddit: RedditClient, settings: Settings) -> list[str]:
    subs = list(settings.seed_subreddits)
    if settings.discover_adjacent_subreddits:
        try:
            adjacent = reddit.discover_adjacent(subs)
        except Exception as e:  # noqa: BLE001
            log.warning("adjacent discovery failed: %s", e)
            adjacent = []
        for name in adjacent:
            if name not in subs:
                subs.append(name)
    return subs


def run_cycle(
    reddit: RedditClient | None = None,
    scorer: Scorer | None = None,
    settings: Settings | None = None,
) -> CycleStats:
    settings = settings or get_settings()
    reddit = reddit or RedditClient()
    scorer = scorer or Scorer()
    stats = CycleStats()

    subreddits = _resolve_subreddits(reddit, settings)
    log.info("polling %d subreddits (dry_run=%s)", len(subreddits), settings.dry_run)

    candidates: list[RedditPost] = []
    for sub in subreddits:
        for post in reddit.fetch_posts(sub, limit=settings.posts_per_listing):
            stats.fetched += 1
            if _matches_keywords(post, settings.problem_keywords):
                candidates.append(post)
                stats.keyword_hits += 1
            if len(candidates) >= settings.candidates_per_cycle:
                break
        if len(candidates) >= settings.candidates_per_cycle:
            break

    existing = _existing_post_ids([c.post_id for c in candidates])
    stats.skipped_duplicate = sum(1 for c in candidates if c.post_id in existing)
    fresh = [c for c in candidates if c.post_id not in existing]

    for post in fresh:
        try:
            result = scorer.score(post.title, post.body, post.subreddit)
        except Exception as e:  # noqa: BLE001
            log.warning("scoring failed for %s: %s", post.post_id, e)
            continue
        stats.scored += 1
        log.info(
            "scored r/%s %s -> %d", post.subreddit, post.post_id, result.relevance_score
        )

        if result.relevance_score < settings.min_score_to_store:
            finder_opportunities_scored_total.labels(stored="false").inc()
            continue
        if settings.dry_run:
            log.info("[dry-run] would store %s (%d)", post.post_id, result.relevance_score)
            finder_opportunities_scored_total.labels(stored="true").inc()
            stats.stored += 1
            continue

        with session_scope() as session:
            already = session.execute(
                select(Opportunity.id).where(Opportunity.post_id == post.post_id)
            ).first()
            if already:
                stats.skipped_duplicate += 1
                continue
            session.add(
                Opportunity(
                    post_id=post.post_id,
                    post_url=post.url,
                    subreddit=post.subreddit,
                    title=post.title,
                    body=post.body,
                    score=result.relevance_score,
                    reason=result.reason,
                    suggested_angle=result.suggested_angle,
                    status="new",
                )
            )
            stats.stored += 1
            finder_opportunities_scored_total.labels(stored="true").inc()

    log.info(
        "cycle done: fetched=%d hits=%d scored=%d stored=%d dup=%d",
        stats.fetched,
        stats.keyword_hits,
        stats.scored,
        stats.stored,
        stats.skipped_duplicate,
    )
    return stats
