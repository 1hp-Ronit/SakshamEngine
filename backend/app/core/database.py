"""Async SQLAlchemy engine/session (SQLite, WAL). One file → trivial reset."""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _ensure_sqlite_dir(url: str) -> None:
    if url.startswith("sqlite") and ":memory:" not in url:
        path = url.split("///", 1)[-1]
        Path(path).parent.mkdir(parents=True, exist_ok=True)


def init_engine(url: str | None = None) -> AsyncEngine:
    global _engine, _sessionmaker
    url = url or get_settings().env.database_url
    _ensure_sqlite_dir(url)
    _engine = create_async_engine(url, future=True)

    if url.startswith("sqlite"):
        @event.listens_for(_engine.sync_engine, "connect")
        def _pragmas(dbapi_conn, _):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()

    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        init_engine()
    assert _engine is not None
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        init_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as session:
        yield session


async def create_all() -> None:
    import app.models  # noqa: F401  (register tables)

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_and_create_all() -> None:
    import app.models  # noqa: F401

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
