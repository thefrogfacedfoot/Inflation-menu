from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Status = Literal["new", "reviewed", "responded", "skipped"]


class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: str
    post_url: str
    subreddit: str
    title: str
    body: str
    score: int
    reason: str
    suggested_angle: str
    status: Status
    created_at: datetime


class StatusUpdate(BaseModel):
    status: Status


class ScoreResult(BaseModel):
    relevance_score: int
    reason: str
    suggested_angle: str
