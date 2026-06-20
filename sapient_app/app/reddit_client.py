from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass

import praw
import prawcore
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class RedditPost:
    post_id: str
    subreddit: str
    title: str
    body: str
    url: str
    created_utc: float


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


class RedditClient:
    def __init__(self) -> None:
        self._reddit = _make_reddit()

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type(_RETRYABLE),
    )
    def _listing(self, subreddit: str, kind: str, limit: int) -> list[praw.models.Submission]:
        sub = self._reddit.subreddit(subreddit)
        listing = sub.new(limit=limit) if kind == "new" else sub.hot(limit=limit)
        try:
            return list(listing)
        except prawcore.exceptions.TooManyRequests as e:
            sleep_for = float(getattr(e.response, "headers", {}).get("retry-after", 30) or 30)
            log.warning("reddit 429, sleeping %.1fs", sleep_for)
            time.sleep(sleep_for)
            raise prawcore.exceptions.RequestException(e, (), {})  # trigger retry

    def fetch_posts(self, subreddit: str, limit: int) -> Iterator[RedditPost]:
        seen: set[str] = set()
        for kind in ("new", "hot"):
            try:
                submissions = self._listing(subreddit, kind, limit)
            except prawcore.exceptions.Redirect:
                log.warning("subreddit r/%s not found, skipping", subreddit)
                return
            except prawcore.exceptions.Forbidden:
                log.warning("subreddit r/%s forbidden (private?), skipping", subreddit)
                return
            for s in submissions:
                if s.id in seen or s.stickied:
                    continue
                seen.add(s.id)
                yield RedditPost(
                    post_id=s.id,
                    subreddit=str(s.subreddit),
                    title=s.title or "",
                    body=s.selftext or "",
                    url=f"https://reddit.com{s.permalink}",
                    created_utc=float(s.created_utc),
                )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(_RETRYABLE),
    )
    def discover_adjacent(self, seeds: list[str], per_seed: int = 5) -> list[str]:
        """Best-effort adjacent discovery: pull authors from seeds and surface
        other subs they post in. PRAW does not expose a sidebar 'related' field
        consistently, so we use author co-occurrence as a proxy."""
        counts: dict[str, int] = {}
        for seed in seeds:
            try:
                authors = {
                    s.author.name
                    for s in self._reddit.subreddit(seed).hot(limit=per_seed)
                    if s.author is not None
                }
            except _RETRYABLE:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("discovery failed for r/%s: %s", seed, e)
                continue
            for author in authors:
                try:
                    for submission in self._reddit.redditor(author).submissions.new(limit=10):
                        name = str(submission.subreddit).lower()
                        if name in {s.lower() for s in seeds}:
                            continue
                        counts[name] = counts.get(name, 0) + 1
                except Exception as e:  # noqa: BLE001
                    log.debug("skip author %s: %s", author, e)
                    continue
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        return [name for name, _ in ranked[:10]]
