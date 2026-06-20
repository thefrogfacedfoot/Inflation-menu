from __future__ import annotations

from datetime import datetime, timezone

import anthropic
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from visibility.config import get_settings
from visibility.sources.base import SourceResult

_RETRYABLE = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


async def query(q: str) -> SourceResult:
    s = get_settings()
    client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key)
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type(_RETRYABLE),
    ):
        with attempt:
            message = await client.messages.create(
                model=s.anthropic_model,
                max_tokens=800,
                system="Answer the user's question as a knowledgeable consumer would.",
                messages=[{"role": "user", "content": q}],
            )
    text = "".join(b.text for b in message.content if getattr(b, "type", None) == "text")
    return SourceResult(raw_response=text, citations=[], fetched_at=datetime.now(timezone.utc))
