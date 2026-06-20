"""Share-of-voice and summary math. Pure functions — easy to test, no DB."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MentionRow:
    """One row per recorded mention; pre-joined with run.source and entity meta."""

    source: str
    entity_id: int
    entity_type: str  # brand | competitor
    is_recommendation: bool
    rank: int | None  # SERP rank; None for LLM


def share_of_voice(brand_count: int, total_count: int) -> float:
    """Fraction of mentions that are the brand's. Returns 0.0 when total is 0
    (no signal yet)."""
    if total_count <= 0:
        return 0.0
    return brand_count / total_count


@dataclass(frozen=True)
class EntitySummary:
    source: str
    entity_id: int
    mention_count: int
    recommendation_count: int
    share_of_voice: float
    avg_rank_when_mentioned: float | None


def summarize(rows: Iterable[MentionRow]) -> list[EntitySummary]:
    """Aggregate mention rows into per-(source, entity) summaries.

    share_of_voice is computed against the BRAND-class total within the source
    — i.e. brand mentions divided by (brand + competitor) mentions for that
    source. For a competitor row, share_of_voice is the competitor's slice of
    the same denominator (so the columns are comparable across rows).
    avg_rank_when_mentioned is averaged across rows where rank is not None;
    None overall if no ranked mentions exist.
    """
    bucket: dict[tuple[str, int], list[MentionRow]] = defaultdict(list)
    totals_by_source: dict[str, int] = defaultdict(int)
    for r in rows:
        bucket[(r.source, r.entity_id)].append(r)
        totals_by_source[r.source] += 1

    out: list[EntitySummary] = []
    for (source, entity_id), items in bucket.items():
        mention_count = len(items)
        rec_count = sum(1 for r in items if r.is_recommendation)
        ranks = [r.rank for r in items if r.rank is not None]
        avg_rank = (sum(ranks) / len(ranks)) if ranks else None
        sov = share_of_voice(mention_count, totals_by_source[source])
        out.append(
            EntitySummary(
                source=source,
                entity_id=entity_id,
                mention_count=mention_count,
                recommendation_count=rec_count,
                share_of_voice=sov,
                avg_rank_when_mentioned=avg_rank,
            )
        )
    return out
