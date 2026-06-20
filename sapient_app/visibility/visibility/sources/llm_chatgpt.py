from __future__ import annotations

from datetime import datetime, timezone

from openai import AsyncOpenAI
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from visibility.config import get_settings
from visibility.sources.base import SourceResult


async def query(q: str) -> SourceResult:
    s = get_settings()
    client = AsyncOpenAI(api_key=s.openai_api_key)
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type(Exception),
    ):
        with attempt:
            resp = await client.chat.completions.create(
                model=s.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "Answer the user's question as a knowledgeable consumer would.",
                    },
                    {"role": "user", "content": q},
                ],
                max_tokens=800,
            )
    text = resp.choices[0].message.content or ""
    return SourceResult(raw_response=text, citations=[], fetched_at=datetime.now(timezone.utc))
