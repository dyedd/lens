import argparse
import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import FrameType

from alembic import command
from alembic.config import Config

from .core.config import settings
from .core.db import create_engine, create_session_factory

SOURCE_PROJECT_DIR = Path(__file__).resolve().parent.parent


def _configure_asyncio_event_loop_policy() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _selector_event_loop_factory() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()


def _uvicorn_loop_factory_path() -> str:
    if sys.platform == "win32":
        return "lens_api.cli:_selector_event_loop_factory"
    return "auto"


def _project_dir() -> Path:
    cwd = Path.cwd()
    if (cwd / "alembic.ini").is_file():
        return cwd
    return SOURCE_PROJECT_DIR


def _alembic_cfg() -> Config:
    project_dir = _project_dir()
    config = Config(str(project_dir / "alembic.ini"))
    config.set_main_option("script_location", str(project_dir / "migrations"))
    return config


def db_upgrade(args: argparse.Namespace) -> None:
    """Upgrade the database to the requested Alembic revision."""
    command.upgrade(_alembic_cfg(), args.revision)


def db_downgrade(args: argparse.Namespace) -> None:
    """Downgrade the database to the requested Alembic revision."""
    command.downgrade(_alembic_cfg(), args.revision)


def db_revision(args: argparse.Namespace) -> None:
    """Create a new Alembic migration revision."""
    command.revision(
        _alembic_cfg(),
        message=args.message,
        autogenerate=args.autogenerate,
    )


def db_current(_args: argparse.Namespace) -> None:
    """Display the current database revision."""
    command.current(_alembic_cfg(), verbose=True)


def db_history(_args: argparse.Namespace) -> None:
    """Display the database migration history."""
    command.history(_alembic_cfg(), verbose=True)


def db_stamp(args: argparse.Namespace) -> None:
    """Stamp the database with the requested Alembic revision."""
    command.stamp(_alembic_cfg(), args.revision)


def serve(args: argparse.Namespace) -> None:
    """Start the Lens API server."""
    import uvicorn

    from .api import create_app
    from .gateway import service

    uvicorn.run(
        create_app(service, ui_static_dir=args.ui_static_dir),
        host=args.host,
        port=args.port,
        loop=_uvicorn_loop_factory_path(),
    )


def dev(_args: argparse.Namespace) -> None:
    """Start the API and UI development servers together."""
    project_dir = _project_dir()
    ui_dir = project_dir / "ui"
    if not ui_dir.is_dir():
        raise RuntimeError(f"UI directory does not exist: {ui_dir}")

    backend_host = "127.0.0.1"
    backend_port = "18080"

    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "lens_api.cli",
            "serve",
            "--host",
            backend_host,
            "--port",
            backend_port,
        ],
        cwd=project_dir,
    )
    frontend_command = "pnpm dev" if os.name == "nt" else ["pnpm", "dev"]
    frontend = subprocess.Popen(frontend_command, cwd=ui_dir, shell=os.name == "nt")

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
        while time.monotonic() < deadline and any(
            process.poll() is None for process in processes
        ):
            time.sleep(0.1)
        for process in processes:
            if process.poll() is None:
                process.kill()

    def handle_signal(signum: int, _frame: FrameType | None) -> None:
        stop_processes()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        while True:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    raise SystemExit(return_code)
            time.sleep(0.25)
    finally:
        stop_processes()


def seed_admin(args: argparse.Namespace) -> None:
    """Create the initial administrator when none exists."""
    from .persistence.repositories import AdminRepository

    async def _run() -> None:
        engine = create_engine(settings.database_url)
        session_factory = create_session_factory(engine)
        store = AdminRepository(session_factory)
        created = await store.ensure_default_admin(args.username, args.password)
        await engine.dispose()
        if created:
            print(f"seeded admin: {args.username}")
        else:
            print("admin user already exists; skipped seed")

    asyncio.run(_run())


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments and dispatch the selected Lens command."""
    _configure_asyncio_event_loop_policy()

    parser = argparse.ArgumentParser(prog="lens", description="Lens CLI")
    subparsers = parser.add_subparsers(dest="group")

    db_parser = subparsers.add_parser("db", help="Database migration commands")
    db_sub = db_parser.add_subparsers(dest="command")

    upgrade_parser = db_sub.add_parser("upgrade", help="Upgrade database to a revision")
    upgrade_parser.add_argument("revision", nargs="?", default="head")
    upgrade_parser.set_defaults(func=db_upgrade)

    down = db_sub.add_parser("downgrade", help="Downgrade database by a revision")
    down.add_argument("revision", nargs="?", default="-1")
    down.set_defaults(func=db_downgrade)

    revision_parser = db_sub.add_parser(
        "revision", help="Create a new migration revision"
    )
    revision_parser.add_argument(
        "-m", "--message", required=True, help="Revision message"
    )
    revision_parser.add_argument(
        "--autogenerate",
        action="store_true",
        default=True,
        help="Auto-detect changes (default)",
    )
    revision_parser.add_argument(
        "--no-autogenerate", dest="autogenerate", action="store_false"
    )
    revision_parser.set_defaults(func=db_revision)

    current_parser = db_sub.add_parser("current", help="Show current revision")
    current_parser.set_defaults(func=db_current)

    history_parser = db_sub.add_parser("history", help="Show revision history")
    history_parser.set_defaults(func=db_history)

    stamp_parser = db_sub.add_parser(
        "stamp", help="Stamp database with a revision without running migrations"
    )
    stamp_parser.add_argument("revision", nargs="?", default="head")
    stamp_parser.set_defaults(func=db_stamp)

    serve_parser = subparsers.add_parser("serve", help="Start the API server")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Listen host")
    serve_parser.add_argument("--port", type=int, default=18080, help="Listen port")
    serve_parser.add_argument(
        "--ui-static-dir",
        default="",
        help="Serve the built UI from this directory",
    )
    serve_parser.set_defaults(func=serve)

    dev_parser = subparsers.add_parser(
        "dev", help="Start API and UI development servers"
    )
    dev_parser.set_defaults(func=dev)

    seed_admin_parser = subparsers.add_parser(
        "seed-admin", help="Create an initial admin user when none exists"
    )
    seed_admin_parser.add_argument("--username", required=True, help="Admin username")
    seed_admin_parser.add_argument("--password", required=True, help="Admin password")
    seed_admin_parser.set_defaults(func=seed_admin)

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
