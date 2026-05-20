from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def normalize_async_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    if normalized.startswith("sqlite://") and not normalized.startswith("sqlite+"):
        return normalized.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+psycopg://", 1)
    if normalized.startswith("postgres://"):
        return normalized.replace("postgres://", "postgresql+psycopg://", 1)
    return normalized


def normalize_sync_database_url(database_url: str) -> str:
    normalized = normalize_async_database_url(database_url)
    if normalized.startswith("sqlite+"):
        return "sqlite://" + normalized.split("://", 1)[1]
    if normalized.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + normalized.split("://", 1)[1]
    return normalized


def is_sqlite_url(database_url: str) -> bool:
    return normalize_async_database_url(database_url).startswith("sqlite")


def is_postgresql_url(database_url: str) -> bool:
    return normalize_async_database_url(database_url).startswith("postgresql")


def create_engine(database_url: str) -> AsyncEngine:
    database_url = normalize_async_database_url(database_url)
    connect_args: dict[str, object] = {}
    if is_sqlite_url(database_url):
        connect_args["timeout"] = 30

    engine = create_async_engine(database_url, future=True, connect_args=connect_args)

    if is_sqlite_url(database_url):
        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=DELETE")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=30000")
            finally:
                cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
