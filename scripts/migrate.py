from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from lens_api.core.config import settings


def _sqlite_db_path() -> Path | None:
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if settings.database_url.startswith(prefix):
            return Path(settings.database_url[len(prefix):])
    return None


def _guard_unmanaged_existing_db() -> None:
    db_path = _sqlite_db_path()
    if db_path is None or not db_path.exists():
        return

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        has_alembic_version = cursor.fetchone() is not None
        if has_alembic_version:
            cursor.execute("SELECT version_num FROM alembic_version")
            version_rows = cursor.fetchall()
            if version_rows:
                return

            raise SystemExit(
                f"Detected invalid Alembic state at {db_path}. "
                "The database has an empty `alembic_version` table. "
                "Remove the existing database file and rerun `python scripts/migrate.py`."
            )

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall() if row[0] != 'sqlite_sequence']
        if tables:
            raise SystemExit(
                f"Detected unmanaged existing database at {db_path}. "
                "Legacy schema compatibility is intentionally unsupported. "
                "Remove the existing database file and rerun `python scripts/migrate.py`."
            )
    finally:
        connection.close()


def main() -> None:
    _guard_unmanaged_existing_db()
    command.upgrade(Config("alembic.ini"), "head")


if __name__ == "__main__":
    main()
