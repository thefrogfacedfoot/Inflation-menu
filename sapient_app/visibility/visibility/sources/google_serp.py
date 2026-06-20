"""SERP source. Backend chosen by SERP_BACKEND env: 'serpapi' or 'brave'."""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from visibility.config import get_settings
from visibility.sources.base import SourceResult


async def query(q: str) -> SourceResult:
    s = get_settings()
    backend = s.serp_backend.lower()
    if backend == "brave":
        return await _query_brave(q)
    return await _query_serpapi(q)


async def _query_serpapi(q: str) -> SourceResult:
    s = get_settings()
    params = {"q": q, "engine": "google", "api_key": s.serpapi_key, "num": 10}
    data = await _get_json("https://serpapi.com/search.json", params=params)
    organic = data.get("organic_results") or []
    items = [
        {
            "rank": i + 1,
            "url": r.get("link", ""),
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
        }
        for i, r in enumerate(organic[:10])
    ]
    return _build_result(items)


async def _query_brave(q: str) -> SourceResult:
    s = get_settings()
    headers = {"X-Subscription-Token": s.brave_api_key, "Accept": "application/json"}
    data = await _get_json(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": q, "count": 10},
        headers=headers,
    )
    results = ((data.get("web") or {}).get("results")) or []
    items = [
        {
            "rank": i + 1,
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "snippet": r.get("description", ""),
        }
        for i, r in enumerate(results[:10])
    ]
    return _build_result(items)


async def _get_json(url: str, *, params: dict, headers: dict | None = None) -> dict:
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type((httpx.HTTPError,)),
    ):
        with attempt:
            async with httpx.AsyncClient(timeout=30) as c:
                resp = await c.get(url, params=params, headers=headers or {})
                if resp.status_code == 429:
                    raise httpx.HTTPStatusError("429", request=resp.request, response=resp)
                resp.raise_for_status()
                return resp.json()
    raise RuntimeError("unreachable")


def _build_result(items: list[dict]) -> SourceResult:
    # raw_response: human-readable concat so detect_mentions can run on it for
    # non-rank-aware queries. Runner uses serp_items for per-rank attribution.
    raw = "\n\n".join(
        f"[{it['rank']}] {it['title']}\n{it['url']}\n{it['snippet']}" for it in items
    )
    citations = [it["url"] for it in items if it.get("url")]
    return SourceResult(
        raw_response=raw,
        citations=citations,
        fetched_at=datetime.now(timezone.utc),
        serp_items=items,
    )
