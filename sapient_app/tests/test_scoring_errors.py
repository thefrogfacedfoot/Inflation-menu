"""Coverage for app.scorer.classify_scoring_error and the poller's
metric-incrementing catch site. We stub the scorer so it raises a
concrete exception per case and assert:

  - finder_scoring_errors_total{reason=<that reason>} ticks by exactly 1
  - finder_opportunities_scored_total is NOT incremented on these paths
    (the error fired BEFORE the relevance branch)

Low-relevance "stored=false" rows live in a separate test path; they go
through the same .score() call but return successfully — see the explicit
no-double-count check at the end.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from app import poller
from app.metrics import (
    finder_opportunities_scored_total,
    finder_scoring_errors_total,
)
from app.scorer import (
    JsonParseError,
    SchemaInvalidError,
    Scorer,
    classify_scoring_error,
)
from app.schemas import ScoreResult


def _counter_value(metric, **labels) -> float:
    """Read one sample from a labeled counter. prometheus_client doesn't
    expose a clean getter, so we walk samples."""
    for m in metric.collect():
        for s in m.samples:
            if s.name.endswith("_total") and s.labels == labels:
                return s.value
    return 0.0


@dataclass
class StubPost:
    post_id: str
    url: str
    subreddit: str
    title: str
    body: str


class StubReddit:
    """Just enough of RedditClient for run_cycle. fetch_posts returns the
    seeded list once; discover_adjacent returns []."""

    def __init__(self, posts: Iterable[StubPost]) -> None:
        self._posts = list(posts)

    def fetch_posts(self, sub: str, *, limit: int):  # noqa: ARG002
        return iter(self._posts)

    def discover_adjacent(self, _seeds):
        return []


def _make_settings() -> object:
    """Minimal settings shim. We avoid the real Settings to keep this test
    independent of pydantic env loading at import time."""
    s = MagicMock()
    s.seed_subreddits = ["testsub"]
    s.problem_keywords = []
    s.posts_per_listing = 5
    s.candidates_per_cycle = 5
    s.dry_run = True
    s.min_score_to_store = 60
    s.discover_adjacent_subreddits = False
    return s


def _make_response(status_code: int) -> httpx.Response:
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx.Response(status_code=status_code, request=req)


# ---- classify_scoring_error ------------------------------------------------


@pytest.mark.parametrize(
    "exc,expected",
    [
        (JsonParseError("no JSON"), "json_parse"),
        (SchemaInvalidError("missing field"), "schema_invalid"),
        (
            anthropic.RateLimitError(
                message="rate", response=_make_response(429), body=None
            ),
            "rate_limited",
        ),
        (
            anthropic.APITimeoutError(request=httpx.Request("POST", "https://x")),
            "timeout",
        ),
        (
            anthropic.InternalServerError(
                message="boom", response=_make_response(500), body=None
            ),
            "upstream_5xx",
        ),
        (RuntimeError("???"), "other"),
    ],
)
def test_classify(exc: BaseException, expected: str) -> None:
    assert classify_scoring_error(exc) == expected


def test_classify_generic_5xx() -> None:
    # A non-InternalServerError API error with status_code 502 still buckets
    # as upstream_5xx — covers gateways/proxies returning 502/503/504.
    e = anthropic.APIStatusError(
        message="bad gateway", response=_make_response(502), body=None
    )
    assert classify_scoring_error(e) == "upstream_5xx"


# ---- poller integration: each error class increments the right label -------


def _seed_post() -> StubPost:
    return StubPost(
        post_id="p1",
        url="https://reddit.com/r/testsub/p1",
        subreddit="testsub",
        title="t",
        body="b",
    )


@pytest.mark.parametrize(
    "exc,expected_reason",
    [
        (JsonParseError("no JSON in response"), "json_parse"),
        (SchemaInvalidError("relevance_score not an int"), "schema_invalid"),
        (
            anthropic.RateLimitError(
                message="rate", response=_make_response(429), body=None
            ),
            "rate_limited",
        ),
        (
            anthropic.APITimeoutError(request=httpx.Request("POST", "https://x")),
            "timeout",
        ),
        (
            anthropic.InternalServerError(
                message="boom", response=_make_response(500), body=None
            ),
            "upstream_5xx",
        ),
        (RuntimeError("kaboom"), "other"),
    ],
)
def test_run_cycle_increments_scoring_errors_per_reason(
    exc: BaseException, expected_reason: str
) -> None:
    scorer = MagicMock(spec=Scorer)
    scorer.score.side_effect = exc

    before_err = _counter_value(
        finder_scoring_errors_total, reason=expected_reason
    )
    before_stored_true = _counter_value(
        finder_opportunities_scored_total, stored="true"
    )
    before_stored_false = _counter_value(
        finder_opportunities_scored_total, stored="false"
    )

    poller.run_cycle(
        reddit=StubReddit([_seed_post()]),
        scorer=scorer,
        settings=_make_settings(),
    )

    after_err = _counter_value(
        finder_scoring_errors_total, reason=expected_reason
    )
    after_stored_true = _counter_value(
        finder_opportunities_scored_total, stored="true"
    )
    after_stored_false = _counter_value(
        finder_opportunities_scored_total, stored="false"
    )

    assert after_err == before_err + 1
    # The error path must NOT also tick the scored counter — that's the
    # whole point of separating the two metrics.
    assert after_stored_true == before_stored_true
    assert after_stored_false == before_stored_false


def test_low_relevance_does_not_increment_scoring_errors() -> None:
    """A scored-but-rejected post (low relevance) is NOT an error. It
    increments opportunities_scored_total{stored=false} only."""
    scorer = MagicMock(spec=Scorer)
    scorer.score.return_value = ScoreResult(
        relevance_score=10, reason="too tangential", suggested_angle="-"
    )

    before_err_other = _counter_value(finder_scoring_errors_total, reason="other")
    before_stored_false = _counter_value(
        finder_opportunities_scored_total, stored="false"
    )

    poller.run_cycle(
        reddit=StubReddit([_seed_post()]),
        scorer=scorer,
        settings=_make_settings(),
    )

    assert (
        _counter_value(finder_scoring_errors_total, reason="other")
        == before_err_other
    )
    assert (
        _counter_value(finder_opportunities_scored_total, stored="false")
        == before_stored_false + 1
    )
