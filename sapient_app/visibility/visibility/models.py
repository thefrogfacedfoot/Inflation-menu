from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from visibility.db import SCHEMA, Base

# JSON column type: JSONB on Postgres, plain JSON on SQLite (for tests).
JsonColumn = JSON().with_variant(JSONB(), "postgresql")


def _schema_kw() -> dict:
    return {"schema": SCHEMA} if SCHEMA else {}


def _table_args(*items, **kw) -> tuple:
    extra = _schema_kw()
    if not items and not kw and not extra:
        return ()
    parts: list = list(items)
    merged = {**kw, **extra}
    if merged:
        parts.append(merged)
    return tuple(parts)


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(20))  # brand | competitor
    aliases: Mapped[list] = mapped_column(JsonColumn, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Query(Base):
    __tablename__ = "queries"
    __table_args__ = _table_args()

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), default="general")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Run(Base):
    __tablename__ = "runs"
    # sqlite_autoincrement: SQLite reuses ROWIDs after DELETE by default, which
    # would let force=True silently land on the same id as the deleted row.
    # Forcing AUTOINCREMENT matches Postgres SEQUENCE semantics and keeps the
    # invariant that a force-rerun produces a new id.
    __table_args__ = _table_args(
        UniqueConstraint("query_id", "source", "run_date", name="uq_runs_query_source_day"),
        Index("ix_runs_source_run_at", "source", "run_at"),
        sqlite_autoincrement=True,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f'{SCHEMA + "." if SCHEMA else ""}queries.id', ondelete="CASCADE"),
    )
    source: Mapped[str] = mapped_column(String(32))
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    run_date: Mapped[date] = mapped_column(Date)
    raw_response: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list] = mapped_column(JsonColumn, default=list)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)

    mentions: Mapped[list["Mention"]] = relationship(
        "Mention", back_populates="run", cascade="all, delete-orphan"
    )


class Mention(Base):
    __tablename__ = "mentions"
    __table_args__ = _table_args(
        Index("ix_mentions_entity_run", "entity_id", "run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f'{SCHEMA + "." if SCHEMA else ""}runs.id', ondelete="CASCADE"),
    )
    entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f'{SCHEMA + "." if SCHEMA else ""}entities.id', ondelete="CASCADE"),
    )
    position: Mapped[int] = mapped_column(Integer)
    context: Mapped[str] = mapped_column(Text)
    sentiment: Mapped[str] = mapped_column(String(16))  # positive|neutral|negative
    is_recommendation: Mapped[bool] = mapped_column(Boolean, default=False)
    # For SERP runs, the result rank where the mention appeared. NULL for LLM.
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    run: Mapped[Run] = relationship("Run", back_populates="mentions")


class SentimentCache(Base):
    __tablename__ = "sentiment_cache"
    __table_args__ = _table_args()

    text_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sentiment: Mapped[str] = mapped_column(String(16))
    is_recommendation: Mapped[bool] = mapped_column(Boolean)
    model: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class DailyCost(Base):
    __tablename__ = "daily_costs"
    __table_args__ = _table_args(
        UniqueConstraint("source", "day", name="uq_daily_costs_source_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    day: Mapped[date] = mapped_column(Date)
    cents_used: Mapped[int] = mapped_column(Integer, default=0)
    runs_count: Mapped[int] = mapped_column(Integer, default=0)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = _table_args(
        Index("ix_tasks_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(64))
    query_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f'{SCHEMA + "." if SCHEMA else ""}queries.id', ondelete="CASCADE"),
    )
    entity_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey(f'{SCHEMA + "." if SCHEMA else ""}entities.id', ondelete="SET NULL"),
        nullable=True,
    )
    related_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Parsed from related_url at task creation for reddit_* kinds; null for
    # non-Reddit kinds (e.g. blog_post). Dashboard reads this column to gate
    # the task against the user's user_active_sub set.
    suggested_subreddit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    recommendation: Mapped[str] = mapped_column(Text)
    # Cross-schema link into the finder's public.opportunities table.
    finder_opportunity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # open | claimed | done | dismissed. Dashboard transitions: open→claimed
    # (via /api/visibility-tasks/:id/claim), claimed→done (via the existing
    # mark-posted route on the synthesized opportunity), open→dismissed.
    status: Mapped[str] = mapped_column(String(16), default="open")
    # Set by the dashboard when a user claims this task. No hard FK across
    # schemas — the dashboard's "user" table lives in a different namespace.
    claimed_by_user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The dashboard post row id once the claim has been marked posted.
    dashboard_post_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # User-supplied free-form reason captured at dismiss time.
    dismiss_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
