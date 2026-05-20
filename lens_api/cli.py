from __future__ import annotations

import argparse
import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Integer, delete, func, insert, inspect, select

from .core.config import settings
from .core.db import Base, create_engine, create_session_factory, is_postgresql_url, is_sqlite_url, normalize_async_database_url
from .persistence import entities as _entities  # noqa: F401

SOURCE_PROJECT_DIR = Path(__file__).resolve().parent.parent
DATABASE_COPY_BATCH_SIZE = 1000


def _project_dir() -> Path:
    env_project_dir = os.environ.get("LENS_PROJECT_DIR", "").strip()
    if env_project_dir:
        return Path(env_project_dir)

    cwd = Path.cwd()
    if (cwd / "alembic.ini").is_file():
        return cwd
    return SOURCE_PROJECT_DIR


def _alembic_cfg() -> Config:
    project_dir = _project_dir()
    config = Config(str(project_dir / "alembic.ini"))
    config.set_main_option("script_location", str(project_dir / "migrations"))
    return config


def _alembic_cfg_for_database(database_url: str) -> Config:
    config = _alembic_cfg()
    config.set_main_option("lens_database_url", database_url)
    return config


def db_upgrade(args: argparse.Namespace) -> None:
    command.upgrade(_alembic_cfg(), args.revision)


def db_downgrade(args: argparse.Namespace) -> None:
    command.downgrade(_alembic_cfg(), args.revision)


def db_revision(args: argparse.Namespace) -> None:
    command.revision(
        _alembic_cfg(),
        message=args.message,
        autogenerate=args.autogenerate,
    )


def db_current(_args: argparse.Namespace) -> None:
    command.current(_alembic_cfg(), verbose=True)


def db_history(_args: argparse.Namespace) -> None:
    command.history(_alembic_cfg(), verbose=True)


def db_stamp(args: argparse.Namespace) -> None:
    command.stamp(_alembic_cfg(), args.revision)


def db_migrate_sqlite_to_postgres(args: argparse.Namespace) -> None:
    sqlite_url = normalize_async_database_url(args.sqlite_url)
    postgres_url = normalize_async_database_url(args.postgres_url)

    if not is_sqlite_url(sqlite_url):
        raise SystemExit("--sqlite-url must be a SQLite SQLAlchemy URL")
    if not is_postgresql_url(postgres_url):
        raise SystemExit("--postgres-url must be a PostgreSQL SQLAlchemy URL")

    include_request_logs = not args.skip_request_logs
    target_has_data = asyncio.run(_target_has_lens_data(postgres_url))
    if target_has_data and not args.replace:
        raise SystemExit(
            "Target PostgreSQL database already contains Lens data. "
            "Use --replace to overwrite it."
        )

    command.upgrade(_alembic_cfg_for_database(sqlite_url), "head")
    command.upgrade(_alembic_cfg_for_database(postgres_url), "head")

    async def _run() -> None:
        source_engine = create_engine(sqlite_url)
        target_engine = create_engine(postgres_url)
        source_session_factory = create_session_factory(source_engine)
        target_session_factory = create_session_factory(target_engine)
        try:
            rows = await _copy_database(
                source_session_factory,
                target_session_factory,
                include_request_logs=include_request_logs,
            )
        finally:
            await source_engine.dispose()
            await target_engine.dispose()

        print("SQLite to PostgreSQL migration completed")
        for table_name in sorted(rows):
            print(f"{table_name}: {rows[table_name]}")

    asyncio.run(_run())


async def _copy_database(
    source_session_factory,
    target_session_factory,
    *,
    include_request_logs: bool,
) -> dict[str, int]:
    tables = list(Base.metadata.sorted_tables)
    copy_tables = tables
    if not include_request_logs:
        copy_tables = [table for table in tables if table.name != "request_logs"]

    async with target_session_factory() as target_session:
        for table in reversed(tables):
            await target_session.execute(delete(table))
        await target_session.commit()

    rows_copied: dict[str, int] = {}
    async with source_session_factory() as source_session:
        async with target_session_factory() as target_session:
            for table in copy_tables:
                rows_copied[table.name] = await _copy_table_rows(
                    source_session,
                    target_session,
                    table,
                )
            await target_session.commit()

    async with target_session_factory() as target_session:
        await _sync_postgres_sequences(target_session, copy_tables)
        await target_session.commit()

    return rows_copied


async def _copy_table_rows(source_session, target_session, table) -> int:
    copied = 0
    offset = 0
    order_columns = list(table.primary_key.columns) or list(table.columns)
    stmt = select(table).order_by(*order_columns)
    while True:
        rows = (
            await source_session.execute(
                stmt.limit(DATABASE_COPY_BATCH_SIZE).offset(offset)
            )
        ).mappings().all()
        if not rows:
            return copied
        payload = [dict(row) for row in rows]
        await target_session.execute(insert(table), payload)
        copied += len(payload)
        offset += len(payload)


async def _target_has_lens_data(database_url: str) -> bool:
    engine = create_engine(database_url)
    try:
        async with engine.connect() as connection:
            existing_table_names = await connection.run_sync(
                lambda sync_connection: set(inspect(sync_connection).get_table_names())
            )
        if not existing_table_names:
            return False

        tables = [
            table
            for table in Base.metadata.sorted_tables
            if table.name in existing_table_names
        ]
        if not tables:
            return False

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            for table in tables:
                count = await session.scalar(select(func.count()).select_from(table))
                if int(count or 0) > 0:
                    return True
        return False
    finally:
        await engine.dispose()


async def _sync_postgres_sequences(target_session, tables) -> None:
    bind = target_session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    for table in tables:
        integer_primary_keys = [
            column
            for column in table.primary_key.columns
            if isinstance(column.type, Integer) and bool(column.autoincrement)
        ]
        for column in integer_primary_keys:
            sequence_name = await target_session.scalar(
                select(func.pg_get_serial_sequence(table.name, column.name))
            )
            if not sequence_name:
                continue
            max_id = await target_session.scalar(select(func.max(column)))
            await target_session.execute(
                select(func.setval(sequence_name, int(max_id or 1), bool(max_id)))
            )


def serve(args: argparse.Namespace) -> None:
    import uvicorn
    if args.reload:
        uvicorn.run("lens_api.gateway.service:app", host=settings.host, port=settings.port, reload=True)
    else:
        from .gateway.service import app
        uvicorn.run(app, host=settings.host, port=settings.port)


def dev(_args: argparse.Namespace) -> None:
    project_dir = _project_dir()
    ui_dir = project_dir / "ui"
    if not ui_dir.is_dir():
        raise RuntimeError(f"UI directory does not exist: {ui_dir}")

    backend_host = "127.0.0.1"
    backend_port = "18080"
    backend_url = f"http://{backend_host}:{backend_port}"

    backend_env = os.environ.copy()
    backend_env["LENS_HOST"] = backend_host
    backend_env["LENS_PORT"] = backend_port
    backend_env.pop("LENS_UI_STATIC_DIR", None)

    frontend_env = os.environ.copy()
    frontend_env["LENS_UI_BACKEND_BASE_URL"] = backend_url
    frontend_env.pop("LENS_UI_STATIC_EXPORT", None)

    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "lens_api.gateway.service:app",
            "--host",
            backend_host,
            "--port",
            backend_port,
            "--reload",
        ],
        cwd=project_dir,
        env=backend_env,
    )
    frontend_command = "pnpm dev" if os.name == "nt" else ["pnpm", "dev"]
    frontend = subprocess.Popen(frontend_command, cwd=ui_dir, env=frontend_env, shell=os.name == "nt")

    processes = (backend, frontend)

    def stop_processes() -> None:
        if os.name == "nt":
            for process in processes:
                if process.poll() is None:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
            return

        for process in processes:
            if process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and any(process.poll() is None for process in processes):
            time.sleep(0.1)
        for process in processes:
            if process.poll() is None:
                process.kill()

    def handle_signal(signum, _frame) -> None:
        stop_processes()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        while True:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    stop_processes()
                    raise SystemExit(return_code)
            time.sleep(0.25)
    finally:
        stop_processes()


def seed_admin(args: argparse.Namespace) -> None:
    from .persistence.admin_store import AdminStore

    async def _run() -> None:
        engine = create_engine(settings.database_url)
        session_factory = create_session_factory(engine)
        store = AdminStore(session_factory)
        created = await store.ensure_default_admin(args.username, args.password)
        await engine.dispose()
        if created:
            print(f"seeded admin: {args.username}")
        else:
            print("admin user already exists; skipped seed")

    asyncio.run(_run())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lens", description="Lens CLI")
    sub = parser.add_subparsers(dest="group")

    db_parser = sub.add_parser("db", help="Database migration commands")
    db_sub = db_parser.add_subparsers(dest="command")

    up = db_sub.add_parser("upgrade", help="Upgrade database to a revision")
    up.add_argument("revision", nargs="?", default="head")
    up.set_defaults(func=db_upgrade)

    down = db_sub.add_parser("downgrade", help="Downgrade database by a revision")
    down.add_argument("revision", nargs="?", default="-1")
    down.set_defaults(func=db_downgrade)

    rev = db_sub.add_parser("revision", help="Create a new migration revision")
    rev.add_argument("-m", "--message", required=True, help="Revision message")
    rev.add_argument("--autogenerate", action="store_true", default=True, help="Auto-detect changes (default)")
    rev.add_argument("--no-autogenerate", dest="autogenerate", action="store_false")
    rev.set_defaults(func=db_revision)

    cur = db_sub.add_parser("current", help="Show current revision")
    cur.set_defaults(func=db_current)

    hist = db_sub.add_parser("history", help="Show revision history")
    hist.set_defaults(func=db_history)

    stmp = db_sub.add_parser("stamp", help="Stamp database with a revision without running migrations")
    stmp.add_argument("revision", nargs="?", default="head")
    stmp.set_defaults(func=db_stamp)

    migrate_pg = db_sub.add_parser(
        "migrate-sqlite-to-postgres",
        help="Copy a SQLite Lens database into PostgreSQL",
    )
    migrate_pg.add_argument("--sqlite-url", required=True, help="Source SQLite database URL")
    migrate_pg.add_argument("--postgres-url", required=True, help="Target PostgreSQL database URL")
    migrate_pg.add_argument(
        "--replace",
        action="store_true",
        help="Clear target Lens tables before copying data",
    )
    migrate_pg.add_argument(
        "--skip-request-logs",
        action="store_true",
        help="Copy configuration and stats but skip request_logs",
    )
    migrate_pg.set_defaults(func=db_migrate_sqlite_to_postgres)

    srv = sub.add_parser("serve", help="Start the API server")
    srv.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes")
    srv.set_defaults(func=serve)

    dev_parser = sub.add_parser("dev", help="Start API and UI development servers")
    dev_parser.set_defaults(func=dev)

    seed = sub.add_parser("seed-admin", help="Create an initial admin user when none exists")
    seed.add_argument("--username", required=True, help="Admin username")
    seed.add_argument("--password", required=True, help="Admin password")
    seed.set_defaults(func=seed_admin)

    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        if args.group == "db":
            db_parser.print_help()
        else:
            parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
