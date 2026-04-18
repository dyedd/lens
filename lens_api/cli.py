from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from .core.config import settings

PROJECT_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI_PATH = PROJECT_DIR / "alembic.ini"


def _alembic_cfg() -> Config:
    return Config(str(ALEMBIC_INI_PATH))


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


def serve(args: argparse.Namespace) -> None:
    import uvicorn
    if args.reload:
        uvicorn.run("lens_api.gateway.service:app", host=settings.host, port=settings.port, reload=True)
    else:
        from .gateway.service import app
        uvicorn.run(app, host=settings.host, port=settings.port)


def seed_admin(args: argparse.Namespace) -> None:
    from .core.db import create_engine, create_session_factory
    from .persistence.admin_store import AdminStore

    async def _run() -> None:
        engine = create_engine(settings.database_url)
        session_factory = create_session_factory(engine)
        store = AdminStore(session_factory)
        await store.ensure_default_admin(args.username, args.password)
        await engine.dispose()
        print(f"seeded admin: {args.username}")

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

    srv = sub.add_parser("serve", help="Start the API server")
    srv.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes")
    srv.set_defaults(func=serve)

    seed = sub.add_parser("seed-admin", help="Create or update an admin user")
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
