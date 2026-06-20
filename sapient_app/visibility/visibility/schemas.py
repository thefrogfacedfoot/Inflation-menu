from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

EntityType = Literal["brand", "competitor"]
TaskStatus = Literal["open", "claimed", "done", "dismissed"]


class EntityIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: EntityType
    aliases: list[str] = []


class EntityOut(EntityIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class QueryIn(BaseModel):
    text: str = Field(min_length=1)
    category: str = "general"
    is_active: bool = True


class QueryOut(QueryIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    query_id: int
    source: str
    run_at: datetime
    run_date: date
    raw_response: str
    citations: list
    cost_cents: int


class EntitySummaryOut(BaseModel):
    source: str
    entity_id: int
    entity_name: str
    entity_type: EntityType
    mention_count: int
    recommendation_count: int
    share_of_voice: float
    avg_rank_when_mentioned: float | None


class TrendPoint(BaseModel):
    bucket: date
    mention_count: int
    recommendation_count: int


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    query_id: int
    entity_id: Optional[int]
    related_url: Optional[str]
    suggested_subreddit: Optional[str]
    recommendation: str
    finder_opportunity_id: Optional[int]
    status: TaskStatus
    claimed_by_user_id: Optional[str]
    claimed_at: Optional[datetime]
    dashboard_post_id: Optional[int]
    dismiss_reason: Optional[str]
    created_at: datetime


class TaskUpdate(BaseModel):
    status: TaskStatus
