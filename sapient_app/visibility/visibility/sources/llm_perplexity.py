from __future__ import annotations

from datetime import datetime, timezone

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from visibility.config import get_settings
from visibility.sources.base import SourceResult

URL = "https://api.perplexity.ai/chat/completions"


async def query(q: str) -> SourceResult:
    s = get_settings()
    payload = {
        "model": s.perplexity_model,
        "messages": [{"role": "user", "content": q}],
        "max_tokens": 800,
    }
    headers = {"Authorization": f"Bearer {s.perplexity_api_key}"}

    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type((httpx.HTTPError,)),
    ):
        with attempt:
            async with httpx.AsyncClient(timeout=60) as c:
                resp = await c.post(URL, json=payload, headers=headers)
                if resp.status_code == 429:
                    raise httpx.HTTPStatusError("429", request=resp.request, response=resp)
                resp.raise_for_status()
                data = resp.json()

    text = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    # Perplexity returns top-level "citations": ["https://...", ...]
    citations = list(data.get("citations") or [])
    return SourceResult(raw_response=text, citations=citations, fetched_at=datetime.now(timezone.utc))
