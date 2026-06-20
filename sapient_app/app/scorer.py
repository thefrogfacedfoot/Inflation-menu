from __future__ import annotations

import json
import logging
import re

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import Settings, get_settings
from app.schemas import ScoreResult

log = logging.getLogger(__name__)


# Typed scoring errors. The poller catches a broad Exception and classifies
# (see classify_scoring_error) so the metrics counter has a bounded `reason`
# label set even when an entirely new failure mode shows up.
class JsonParseError(ValueError):
    """Model response did not contain a parseable JSON object."""


class SchemaInvalidError(ValueError):
    """JSON parsed, but the fields we need are missing or the wrong type."""

SYSTEM_PROMPT = """You are a marketing analyst who finds genuine product-fit moments
in Reddit threads. You score how likely a Reddit post represents a real opportunity
for the product described below to be helpfully mentioned.

Product name: {product_name}
Product description:
{product_description}

Problems the product solves (keywords):
{keywords}

Scoring rubric (0-100):
- 0-39: not relevant or off-topic
- 40-59: tangentially related, no real fit
- 60-79: relevant — the user is describing a problem this product addresses
- 80-100: high intent — the user is actively asking for a solution like this

You must respond with ONLY a JSON object of the form:
{{"relevance_score": <int>, "reason": "<one sentence>", "suggested_angle": "<one to two sentences on how to reply helpfully, not spammy>"}}
Do not include markdown fences or any other text.
"""


def _build_system(s: Settings) -> str:
    return SYSTEM_PROMPT.format(
        product_name=s.product_name,
        product_description=s.product_description,
        keywords=", ".join(s.problem_keywords) or "(none)",
    )


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse(text: str) -> ScoreResult:
    match = _JSON_RE.search(text)
    if not match:
        raise JsonParseError(f"no JSON object in model response: {text!r}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise JsonParseError(f"could not decode JSON: {e}") from e
    if not isinstance(data, dict):
        raise SchemaInvalidError("top-level value is not an object")
    if "relevance_score" not in data:
        raise SchemaInvalidError("missing relevance_score field")
    try:
        score = int(data["relevance_score"])
    except (TypeError, ValueError) as e:
        raise SchemaInvalidError(
            f"relevance_score not an int: {data.get('relevance_score')!r}"
        ) from e
    score = max(0, min(100, score))
    return ScoreResult(
        relevance_score=score,
        reason=str(data.get("reason", "")).strip(),
        suggested_angle=str(data.get("suggested_angle", "")).strip(),
    )


def classify_scoring_error(exc: BaseException) -> str:
    """Map a scorer exception to one of the bounded `reason` labels on
    finder_scoring_errors_total. Order matters: typed parse/schema errors
    come from our own _parse; upstream API errors come from the Anthropic
    SDK. Everything unrecognized is 'other' — we keep the catchall so the
    counter is honest about unknown failure modes."""
    if isinstance(exc, JsonParseError):
        return "json_parse"
    if isinstance(exc, SchemaInvalidError):
        return "schema_invalid"
    if isinstance(exc, anthropic.RateLimitError):
        return "rate_limited"
    if isinstance(exc, anthropic.APITimeoutError):
        return "timeout"
    if isinstance(exc, anthropic.InternalServerError):
        return "upstream_5xx"
    # Some other anthropic.APIStatusError with a 5xx code — bucket as upstream.
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and 500 <= status < 600:
        return "upstream_5xx"
    return "other"


_RETRYABLE = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


class Scorer:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        self._system = _build_system(self._settings)

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type(_RETRYABLE),
    )
    def score(self, title: str, body: str, subreddit: str) -> ScoreResult:
        user = (
            f"Subreddit: r/{subreddit}\n"
            f"Title: {title}\n\n"
            f"Body:\n{body[:4000] if body else '(no body)'}"
        )
        message = self._client.messages.create(
            model=self._settings.scoring_model,
            max_tokens=400,
            system=self._system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
        return _parse(text)
