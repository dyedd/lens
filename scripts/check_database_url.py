from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncEngine

from lens_api.core.db import create_engine, normalize_async_database_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
TIMEOUT_SECONDS = 10.0


def load_database_url() -> str:
    """Load the configured database URL from the project environment file."""
    if not ENV_FILE.exists():
        raise ValueError(f"{ENV_FILE} does not exist")

    value = dotenv_values(ENV_FILE).get("LENS_DATABASE_URL")
    if not value or not value.strip():
        raise ValueError("LENS_DATABASE_URL is missing or empty in .env")

    return value


def mask_error_message(message: str, database_url: str) -> str:
    """Remove database URLs and credentials from an error message."""
    masked = message
    normalized_url = normalize_async_database_url(database_url)
    for secret in {database_url, normalized_url}:
        masked = masked.replace(secret, "<LENS_DATABASE_URL>")

    try:
        parsed_url = make_url(normalized_url)
    except ArgumentError:
        return masked

    for secret in (parsed_url.username, parsed_url.password):
        if secret:
            masked = masked.replace(secret, "<masked>")

    return masked


async def ping_database(engine: AsyncEngine) -> None:
    """Execute a minimal query against a database engine."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def check_database_url(database_url: str) -> None:
    """Verify that a database URL can be reached within the timeout."""
    engine = create_engine(database_url)
    try:
        await asyncio.wait_for(ping_database(engine), timeout=TIMEOUT_SECONDS)
    finally:
        await engine.dispose()


def main() -> int:
    """Run the database connectivity check and return a process exit code."""
    database_url = ""
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        database_url = load_database_url()
        asyncio.run(check_database_url(database_url))
    except TimeoutError:
        print(
            f"FAILED: LENS_DATABASE_URL timed out after {TIMEOUT_SECONDS:g} seconds",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        message = (
            mask_error_message(str(exc), database_url) if database_url else str(exc)
        )
        print(f"FAILED: {type(exc).__name__}: {message}", file=sys.stderr)
        return 1

    print("OK: .env LENS_DATABASE_URL is reachable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
