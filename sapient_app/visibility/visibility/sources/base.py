"""Source plugin contract.

Each source module exposes a single coroutine:

    async def query(q: str) -> SourceResult

SourceResult.citations is `list[str]` per spec (URLs). SERP-style sources may
additionally populate `serp_items` with rank/title/snippet so the runner can
attribute per-result rank to detected mentions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, Protocol


@dataclass
class SourceResult:
    raw_response: str
    citations: list[str]
    fetched_at: datetime
    serp_items: list[dict] | None = field(default=None)


class Source(Protocol):
    async def query(self, q: str) -> SourceResult: ...


_QueryFn = Callable[[str], Awaitable[SourceResult]]


def get_source(name: str) -> _QueryFn:
    """Lazy import so missing optional SDKs don't break unrelated sources."""
    if name == "chatgpt":
        from . import llm_chatgpt

        return llm_chatgpt.query
    if name == "claude":
        from . import llm_claude

        return llm_claude.query
    if name == "gemini":
        from . import llm_gemini

        return llm_gemini.query
    if name == "perplexity":
        from . import llm_perplexity

        return llm_perplexity.query
    if name == "serp":
        from . import google_serp

        return google_serp.query
    if name == "reddit_search":
        from . import reddit_search

        return reddit_search.query
    raise ValueError(f"unknown source: {name}")
