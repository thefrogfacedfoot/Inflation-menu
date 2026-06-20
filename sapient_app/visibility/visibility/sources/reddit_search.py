from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import praw
import prawcore
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from visibility.config import get_settings
from visibility.sources.base import SourceResult

_RETRYABLE = (
    prawcore.exceptions.ServerError,
    prawcore.exceptions.RequestException,
    prawcore.exceptions.ResponseException,
)


def _make_reddit() -> praw.Reddit:
    s = get_settings()
    return praw.Reddit(
        client_id=s.reddit_client_id,
        client_secret=s.reddit_client_secret,
        user_agent=s.reddit_user_agent,
        check_for_async=False,
    )


def _fetch_blocking(q: str) -> list[dict]:
    reddit = _make_reddit()
    sub = reddit.subreddit("all")
    by_id: dict[str, dict] = {}
    # Two passes per the spec: relevance (all-time) + top (last year).
    for kind in (("relevance", "all"), ("top", "year")):
        sort, time_filter = kind
        for s in sub.search(q, sort=sort, time_filter=time_filter, limit=15):
            if s.id in by_id:
                continue
            by_id[s.id] = {
                "id": s.id,
                "subreddit": str(s.subreddit),
                "title": s.title or "",
                "selftext": (s.selftext or "")[:1500],
                "permalink": f"https://reddit.com{s.permalink}",
                "score": int(s.score or 0),
                "sort": sort,
            }
    return list(by_id.values())


async def query(q: str) -> SourceResult:
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type(_RETRYABLE),
    ):
        with attempt:
            items = await asyncio.to_thread(_fetch_blocking, q)

    raw = "\n\n".join(
        f"r/{it['subreddit']} (score {it['score']}, sort {it['sort']})\n"
        f"{it['title']}\n{it['permalink']}\n{it['selftext']}"
        for it in items
    )
    citations = [it["permalink"] for it in items]
    return SourceResult(raw_response=raw, citations=citations, fetched_at=datetime.now(timezone.utc))
