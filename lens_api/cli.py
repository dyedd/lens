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

from .core.config import settings

SOURCE_PROJECT_DIR = Path(__file__).resolve().parent.parent


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
    from .core.db import create_engine, create_session_factory
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
