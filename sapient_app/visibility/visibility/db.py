from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.engine import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from visibility.config import get_settings


def _schema() -> str | None:
    s = get_settings().visibility_db_schema.strip()
    return s or None


SCHEMA = _schema()


class Base(DeclarativeBase):
    """Single declarative base. Models override __table_args__ to inject the
    schema only when SCHEMA is set, so the same models work on SQLite tests
    (no schema) and Postgres prod (schema='visibility')."""


def _make_engine() -> Engine:
    url = get_settings().database_url
    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)


engine = _make_engine()


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    # FK enforcement on SQLite for tests
    if engine.dialect.name == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def ensure_schema() -> None:
    if SCHEMA is None or engine.dialect.name != "postgresql":
        return
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))


def init_db() -> None:
    ensure_schema()
    from visibility import models  # noqa: F401  ensure models registered

    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
