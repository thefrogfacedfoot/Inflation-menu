from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query as QueryParam
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from visibility.config import SOURCES
from visibility.costs import CostCapReached
from visibility.db import get_session, init_db
from visibility.models import Entity, Mention, Query, Run, Task
from visibility.runner import run_query
from visibility.scheduler import build_scheduler
from visibility.schemas import (
    EntityIn,
    EntityOut,
    EntitySummaryOut,
    QueryIn,
    QueryOut,
    RunOut,
    TaskOut,
    TaskUpdate,
    TrendPoint,
)
from visibility.sov import MentionRow, summarize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    scheduler = build_scheduler()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Visibility Tracker", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------- entities ----------


@app.post("/entities", response_model=EntityOut, status_code=201)
def create_entity(payload: EntityIn, session: Annotated[Session, Depends(get_session)]) -> Entity:
    e = Entity(name=payload.name, type=payload.type, aliases=list(payload.aliases))
    session.add(e)
    session.commit()
    session.refresh(e)
    return e


@app.get("/entities", response_model=list[EntityOut])
def list_entities(session: Annotated[Session, Depends(get_session)]) -> list[Entity]:
    return list(session.execute(select(Entity).order_by(Entity.id)).scalars())


@app.patch("/entities/{entity_id}", response_model=EntityOut)
def update_entity(
    entity_id: int, payload: EntityIn, session: Annotated[Session, Depends(get_session)]
) -> Entity:
    e = session.get(Entity, entity_id)
    if e is None:
        raise HTTPException(404, "not found")
    e.name = payload.name
    e.type = payload.type
    e.aliases = list(payload.aliases)
    session.commit()
    session.refresh(e)
    return e


@app.delete("/entities/{entity_id}", status_code=204)
def delete_entity(entity_id: int, session: Annotated[Session, Depends(get_session)]) -> None:
    e = session.get(Entity, entity_id)
    if e is None:
        raise HTTPException(404, "not found")
    session.delete(e)
    session.commit()


# ---------- queries ----------


@app.post("/queries", response_model=QueryOut, status_code=201)
def create_query(payload: QueryIn, session: Annotated[Session, Depends(get_session)]) -> Query:
    q = Query(text=payload.text, category=payload.category, is_active=payload.is_active)
    session.add(q)
    session.commit()
    session.refresh(q)
    return q


@app.get("/queries", response_model=list[QueryOut])
def list_queries(session: Annotated[Session, Depends(get_session)]) -> list[Query]:
    return list(session.execute(select(Query).order_by(Query.id)).scalars())


@app.patch("/queries/{query_id}", response_model=QueryOut)
def update_query(
    query_id: int, payload: QueryIn, session: Annotated[Session, Depends(get_session)]
) -> Query:
    q = session.get(Query, query_id)
    if q is None:
        raise HTTPException(404, "not found")
    q.text = payload.text
    q.category = payload.category
    q.is_active = payload.is_active
    session.commit()
    session.refresh(q)
    return q


@app.delete("/queries/{query_id}", status_code=204)
def delete_query(query_id: int, session: Annotated[Session, Depends(get_session)]) -> None:
    q = session.get(Query, query_id)
    if q is None:
        raise HTTPException(404, "not found")
    session.delete(q)
    session.commit()


# ---------- runs ----------


@app.get("/runs", response_model=list[RunOut])
def list_runs(
    session: Annotated[Session, Depends(get_session)],
    query_id: int | None = QueryParam(default=None),
    source: str | None = QueryParam(default=None),
    since: datetime | None = QueryParam(default=None),
    limit: int = QueryParam(default=100, ge=1, le=500),
) -> list[Run]:
    stmt = select(Run)
    if query_id is not None:
        stmt = stmt.where(Run.query_id == query_id)
    if source:
        stmt = stmt.where(Run.source == source)
    if since:
        stmt = stmt.where(Run.run_at >= since)
    stmt = stmt.order_by(Run.run_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars())


# ---------- visibility ----------


@app.get("/visibility/summary", response_model=list[EntitySummaryOut])
def visibility_summary(
    session: Annotated[Session, Depends(get_session)],
    since: datetime | None = QueryParam(default=None),
) -> list[EntitySummaryOut]:
    since = since or datetime.now(timezone.utc) - timedelta(days=30)
    rows = session.execute(
        select(Run.source, Mention.entity_id, Entity.type, Mention.is_recommendation, Mention.rank)
        .join(Mention, Mention.run_id == Run.id)
        .join(Entity, Entity.id == Mention.entity_id)
        .where(Run.run_at >= since)
    ).all()
    summaries = summarize(
        [
            MentionRow(
                source=r[0],
                entity_id=r[1],
                entity_type=r[2],
                is_recommendation=bool(r[3]),
                rank=r[4],
            )
            for r in rows
        ]
    )
    name_by_id = {
        e.id: (e.name, e.type)
        for e in session.execute(select(Entity)).scalars()
    }
    return [
        EntitySummaryOut(
            source=s.source,
            entity_id=s.entity_id,
            entity_name=name_by_id.get(s.entity_id, ("?", "brand"))[0],
            entity_type=name_by_id.get(s.entity_id, ("?", "brand"))[1],  # type: ignore[arg-type]
            mention_count=s.mention_count,
            recommendation_count=s.recommendation_count,
            share_of_voice=s.share_of_voice,
            avg_rank_when_mentioned=s.avg_rank_when_mentioned,
        )
        for s in summaries
    ]


@app.get("/visibility/trend", response_model=list[TrendPoint])
def visibility_trend(
    session: Annotated[Session, Depends(get_session)],
    entity_id: int = QueryParam(...),
    source: str | None = QueryParam(default=None),
    bucket: str = QueryParam(default="day", pattern="^(day|week)$"),
    since: datetime | None = QueryParam(default=None),
) -> list[TrendPoint]:
    since = since or datetime.now(timezone.utc) - timedelta(days=90)
    bucket_expr = (
        func.date_trunc(bucket, Run.run_at) if session.bind.dialect.name == "postgresql"
        else func.date(Run.run_at)
    )
    rows = session.execute(
        select(
            bucket_expr.label("b"),
            func.count(Mention.id).label("n"),
            func.sum(func.cast(Mention.is_recommendation, type_=__bool_int(session))).label("r"),
        )
        .join(Mention, Mention.run_id == Run.id)
        .where(Mention.entity_id == entity_id, Run.run_at >= since)
        .where(Run.source == source if source else True)
        .group_by("b")
        .order_by("b")
    ).all()
    return [
        TrendPoint(
            bucket=_as_date(r[0]),
            mention_count=int(r[1] or 0),
            recommendation_count=int(r[2] or 0),
        )
        for r in rows
    ]


def __bool_int(session: Session):
    # Postgres SUMs booleans natively; SQLite needs an INTEGER cast.
    from sqlalchemy import Integer

    return Integer()


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


# ---------- manual trigger ----------


@app.post("/poll-now")
async def poll_now(
    session: Annotated[Session, Depends(get_session)],
    query_id: int = QueryParam(...),
    source: str = QueryParam(...),
    force: bool = QueryParam(default=False),
) -> dict:
    if source not in SOURCES:
        raise HTTPException(400, f"unknown source: {source}")
    try:
        run = await run_query(session, query_id, source, force=force)
    except CostCapReached as e:
        raise HTTPException(429, str(e)) from e
    if run is None:
        return {"status": "skipped"}
    return {"status": "ok", "run_id": run.id, "skipped_idempotent": False}


# ---------- tasks ----------


@app.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    session: Annotated[Session, Depends(get_session)],
    status: str | None = QueryParam(default=None),
) -> list[Task]:
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    return list(session.execute(stmt.order_by(Task.created_at.desc())).scalars())


@app.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int, payload: TaskUpdate, session: Annotated[Session, Depends(get_session)]
) -> Task:
    t = session.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "not found")
    t.status = payload.status
    session.commit()
    session.refresh(t)
    return t
