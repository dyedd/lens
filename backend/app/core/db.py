from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def to_async_database_url(database_url: str) -> str:
    """Convert a database URL for the asynchronous SQLAlchemy engine."""
    trimmed_url = database_url.strip()
    if trimmed_url.startswith("sqlite://") and not trimmed_url.startswith("sqlite+"):
        return trimmed_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if trimmed_url.startswith("postgresql://"):
        return trimmed_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if trimmed_url.startswith("postgres://"):
        return trimmed_url.replace("postgres://", "postgresql+psycopg://", 1)
    return trimmed_url


def to_sync_database_url(database_url: str) -> str:
    """Convert a database URL for synchronous database clients."""
    async_url = to_async_database_url(database_url)
    if async_url.startswith("sqlite+"):
        return "sqlite://" + async_url.split("://", 1)[1]
    if async_url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + async_url.split("://", 1)[1]
    return async_url


def create_engine(database_url: str) -> AsyncEngine:
    """Create an asynchronous database engine for the configured URL."""
    database_url = to_async_database_url(database_url)
    is_sqlite = database_url.startswith("sqlite")
    connect_args: dict[str, object] = {"timeout": 30} if is_sqlite else {}

    engine = create_async_engine(database_url, connect_args=connect_args)

    if is_sqlite:

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=DELETE")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=30000")
            finally:
                cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an asynchronous session factory for an engine."""
    return async_sessionmaker(engine, expire_on_commit=False)
