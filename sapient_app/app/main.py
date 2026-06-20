from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app._obs import CorrelationIdMiddleware, configure_structlog, get_logger
from app.config import get_settings
from app.db import engine, get_session, init_db
from app.metrics import start_sidecar
from app.models import Opportunity
from app.poller import run_cycle
from app.schemas import OpportunityOut, StatusUpdate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
configure_structlog("finder")
log = get_logger("opportunity-finder")


async def _poll_forever() -> None:
    settings = get_settings()
    interval = max(1, settings.poll_interval_minutes) * 60
    while True:
        try:
            await asyncio.to_thread(run_cycle)
        except Exception:
            log.exception("poll cycle crashed; backing off")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_sidecar()
    task = asyncio.create_task(_poll_forever(), name="reddit-poller")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


app = FastAPI(title="Reddit Opportunity Finder", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)


def _schema_check() -> tuple[bool, str | None]:
    """Schema-level readiness probe: pg_isready (compose) only verifies the
    protocol layer; this catches "DB up but migrations didn't land." The
    inspect() API works against Postgres and SQLite identically, so tests
    against in-memory SQLite still cover the routing — they just need to
    materialize the table first.

    Returns (ok, failure_reason). Tests monkeypatch this directly to
    simulate the failure branch without yanking the DB."""
    try:
        ins = inspect(engine)
        if not ins.has_table("opportunities"):
            return False, "public.opportunities missing"
    except Exception as e:  # noqa: BLE001
        return False, f"db_query_failed: {type(e).__name__}: {e}"
    return True, None


@app.get("/health")
def health() -> JSONResponse:
    ok, reason = _schema_check()
    if not ok:
        return JSONResponse(
            {"status": "error", "service": "finder", "check": reason},
            status_code=503,
        )
    return JSONResponse({"status": "ok", "service": "finder"})


@app.get("/opportunities", response_model=list[OpportunityOut])
def list_opportunities(
    session: Annotated[Session, Depends(get_session)],
    subreddit: str | None = Query(default=None),
    min_score: int = Query(default=0, ge=0, le=100),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Opportunity]:
    stmt = select(Opportunity)
    if subreddit:
        stmt = stmt.where(Opportunity.subreddit == subreddit)
    if min_score:
        stmt = stmt.where(Opportunity.score >= min_score)
    if status:
        stmt = stmt.where(Opportunity.status == status)
    stmt = stmt.order_by(Opportunity.score.desc(), Opportunity.id.desc()).limit(limit).offset(offset)
    return list(session.execute(stmt).scalars())


@app.patch("/opportunities/{opportunity_id}", response_model=OpportunityOut)
def update_status(
    opportunity_id: int,
    payload: StatusUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> Opportunity:
    opp = session.get(Opportunity, opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="not found")
    opp.status = payload.status
    session.commit()
    session.refresh(opp)
    return opp


@app.post("/poll-once")
def poll_once() -> dict[str, int]:
    stats = run_cycle()
    return {
        "fetched": stats.fetched,
        "keyword_hits": stats.keyword_hits,
        "scored": stats.scored,
        "stored": stats.stored,
        "skipped_duplicate": stats.skipped_duplicate,
    }
