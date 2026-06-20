from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import google.generativeai as genai
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from visibility.config import get_settings
from visibility.sources.base import SourceResult


async def query(q: str) -> SourceResult:
    s = get_settings()
    genai.configure(api_key=s.google_api_key)
    model = genai.GenerativeModel(s.gemini_model)

    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type(Exception),
    ):
        with attempt:
            # google-generativeai's async surface is limited; offload the blocking call.
            resp = await asyncio.to_thread(
                model.generate_content,
                q,
                generation_config={"max_output_tokens": 800},
            )
    text = getattr(resp, "text", "") or ""
    return SourceResult(raw_response=text, citations=[], fetched_at=datetime.now(timezone.utc))
