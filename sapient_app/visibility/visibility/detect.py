"""
Entity-mention detection — same Unicode word-boundary engine as the
dashboard's product-detect, generalised to arbitrary entities + aliases.

Public surface:
    find_mention_positions(text, entities) -> list[MentionMatch]   (pure)
    SentimentClassifier                                            (DB-backed cache)
    detect_mentions(text, entities, classifier)                    (async wrapper)
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Iterable, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from visibility.models import Entity, SentimentCache

log = logging.getLogger(__name__)

_REGEX_SPECIAL = re.compile(r"[.*+?^${}()|[\]\\]")
CONTEXT_RADIUS = 100


def _escape(s: str) -> str:
    return _REGEX_SPECIAL.sub(lambda m: "\\" + m.group(0), s)


def _build_pattern(aliases: Iterable[str]) -> re.Pattern[str]:
    # One pattern per entity, alternation of all aliases.
    #
    # Boundary class [^\W_] = "word char that isn't underscore" = letters +
    # digits only (Unicode-aware). Underscore is therefore treated AS a
    # boundary, so "acme" matches "acme_dev" — same behavior as the
    # dashboard's JS detector (which uses [\p{L}\p{N}] lookarounds).
    parts = [_escape(a) for a in aliases if a]
    if not parts:
        return re.compile(r"(?!x)x")  # never matches
    inner = "|".join(parts)
    return re.compile(rf"(?<![^\W_])({inner})(?![^\W_])", re.IGNORECASE | re.UNICODE)


@dataclass(frozen=True)
class MentionMatch:
    entity_id: int
    position: int
    matched: str
    context: str


def find_mention_positions(text: str, entities: Iterable[Entity]) -> list[MentionMatch]:
    if not text:
        return []
    out: list[MentionMatch] = []
    for e in entities:
        aliases = [e.name, *(e.aliases or [])]
        pat = _build_pattern(aliases)
        for m in pat.finditer(text):
            start = max(0, m.start() - CONTEXT_RADIUS)
            end = min(len(text), m.end() + CONTEXT_RADIUS)
            out.append(
                MentionMatch(
                    entity_id=e.id,
                    position=m.start(),
                    matched=m.group(0),
                    context=text[start:end],
                )
            )
    return out


# ---------- sentiment / recommendation classification ----------


@dataclass(frozen=True)
class SentimentResult:
    sentiment: str  # positive | neutral | negative
    is_recommendation: bool


def _context_hash(context: str) -> str:
    return hashlib.sha256(context.encode("utf-8")).hexdigest()


class _LLM(Protocol):
    async def classify(self, prompt: str) -> str: ...


class SentimentClassifier:
    """Persistent cache keyed by (sha256(context), entity_id). On miss, calls
    the injected LLM and stores the result."""

    def __init__(
        self,
        session: Session,
        llm: _LLM,
        *,
        model_name: str = "claude-opus-4-7",
    ) -> None:
        self.session = session
        self.llm = llm
        self.model_name = model_name

    async def classify(self, context: str, entity_id: int, entity_name: str) -> SentimentResult:
        key = _context_hash(context)
        cached = self.session.get(SentimentCache, (key, entity_id))
        if cached:
            return SentimentResult(cached.sentiment, cached.is_recommendation)

        prompt = (
            f"You are scoring a single mention of \"{entity_name}\" in a text.\n"
            f"Return ONLY JSON: {{\"sentiment\":\"positive|neutral|negative\",\"is_recommendation\":true|false}}.\n"
            "is_recommendation is true only if the text actively suggests using or buying it.\n\n"
            f"Context:\n{context}"
        )
        raw = await self.llm.classify(prompt)
        parsed = _parse_sentiment_json(raw)

        self.session.merge(
            SentimentCache(
                text_hash=key,
                entity_id=entity_id,
                sentiment=parsed.sentiment,
                is_recommendation=parsed.is_recommendation,
                model=self.model_name,
            )
        )
        return parsed


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_sentiment_json(raw: str) -> SentimentResult:
    m = _JSON_RE.search(raw or "")
    if not m:
        return SentimentResult("neutral", False)
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return SentimentResult("neutral", False)
    sentiment = str(data.get("sentiment", "neutral")).lower()
    if sentiment not in {"positive", "neutral", "negative"}:
        sentiment = "neutral"
    return SentimentResult(sentiment=sentiment, is_recommendation=bool(data.get("is_recommendation")))


# ---------- top-level helper ----------


@dataclass(frozen=True)
class DetectedMention:
    entity_id: int
    position: int
    context: str
    sentiment: str
    is_recommendation: bool


async def detect_mentions(
    text: str,
    entities: list[Entity],
    classifier: SentimentClassifier,
) -> list[DetectedMention]:
    matches = find_mention_positions(text, entities)
    name_by_id = {e.id: e.name for e in entities}
    out: list[DetectedMention] = []
    for m in matches:
        s = await classifier.classify(m.context, m.entity_id, name_by_id.get(m.entity_id, ""))
        out.append(
            DetectedMention(
                entity_id=m.entity_id,
                position=m.position,
                context=m.context,
                sentiment=s.sentiment,
                is_recommendation=s.is_recommendation,
            )
        )
    return out


def load_entities(session: Session) -> list[Entity]:
    return list(session.execute(select(Entity)).scalars())
