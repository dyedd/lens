import argparse
import asyncio
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import FrameType

from alembic import command
from alembic.config import Config

from .core.auth import validate_admin_password
from .core.config import settings
from .core.db import create_engine, create_session_factory, to_async_database_url

SOURCE_BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ADMIN_USERNAME = "admin"


def _admin_password_argument(value: str) -> str:
    try:
        return validate_admin_password(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _write_private_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    descriptor = os.open(
        temporary_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            descriptor = -1
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
        os.chmod(path, 0o600)
        if os.name != "nt":
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _selector_event_loop_factory() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()


def _uvicorn_loop_factory_path() -> str:
    if sys.platform == "win32":
        return "app.cli:_selector_event_loop_factory"
    return "auto"


def _backend_dir() -> Path:
    cwd = Path.cwd()
    if (cwd / "alembic.ini").is_file():
        return cwd
    return SOURCE_BACKEND_DIR


def _repo_dir() -> Path:
    """Return the repository root, which holds `.env`, `data/`, and `frontend/`."""
    return _backend_dir().parent


def _alembic_cfg() -> Config:
    backend_dir = _backend_dir()
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "app" / "alembic"))
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


def _seed_initial_admin(
    username: str = DEFAULT_ADMIN_USERNAME,
    password: str | None = None,
    *,
    password_file: Path | None = None,
) -> bool:
    """Create the admin when none exists; return whether a new account was written."""
    from .persistence.repositories import AdminRepository

    generated = password is None
    password = password or secrets.token_urlsafe(24)
    # A password the operator supplied needs no file, and a generated one
    # lands where the Docker deployment documents it; see README.md.
    seed_file = password_file
    if seed_file is None and generated:
        seed_file = _data_dir() / "admin-password"
    created = False
    publish_initial_password = (
        (lambda: _write_private_text(seed_file, f"{password}\n"))
        if seed_file is not None
        else None
    )

    async def _run() -> None:
        nonlocal created
        engine = create_engine(settings.database_url)
        session_factory = create_session_factory(engine)
        try:
            created = await AdminRepository(session_factory).ensure_default_admin(
                username,
                password,
                publish_initial_password=publish_initial_password,
            )
        finally:
            await engine.dispose()

    asyncio.run(
        _run(),
        loop_factory=(
            _selector_event_loop_factory if sys.platform == "win32" else None
        ),
    )
    if created:
        print(f"seeded admin: {username}")
        if seed_file is not None:
            print(f"initial admin password written to: {seed_file}")
    return created


def _pnpm_command(args: list[str]) -> str | list[str]:
    # pnpm installs as a `.cmd` shim on Windows, which resolves through the shell
    # but not as a bare executable.
    if os.name == "nt":
        return f"pnpm {' '.join(args)}"
    return ["pnpm", *args]


def _pnpm_popen(
    frontend_dir: Path, args: list[str], env: dict[str, str]
) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        _pnpm_command(args),
        cwd=frontend_dir,
        shell=os.name == "nt",
        env=env,
        # Give the frontend its own process group so stopping it also stops the
        # pnpm and Vite processes it spawns.
        start_new_session=os.name != "nt",
    )


def _run_pnpm(frontend_dir: Path, *args: str) -> None:
    subprocess.run(
        _pnpm_command(list(args)),
        cwd=frontend_dir,
        shell=os.name == "nt",
        check=True,
    )


def _data_dir() -> Path:
    """Return where the deployment keeps its data files, matching the Docker volume."""
    # pydantic-settings resolves a relative SQLite path against the working
    # directory, so the directory before it is what this process writes into.
    database_url = to_async_database_url(settings.database_url)
    sqlite_prefix = "sqlite+aiosqlite:///"
    if sqlite_prefix in database_url:
        return Path(database_url.split(sqlite_prefix, 1)[1]).parent.resolve()
    return Path(os.getenv("LENS_DATA_DIR", "/app/data"))


def serve(args: argparse.Namespace) -> None:
    """Start the Lens API server."""
    import uvicorn

    from .api import create_app

    uvicorn.run(
        create_app(ui_static_dir=args.ui_static_dir),
        host=args.host,
        port=args.port,
        loop=_uvicorn_loop_factory_path(),
    )


def migrate(_args: argparse.Namespace | None) -> None:
    """Upgrade the database, then write the admin or its initial password."""
    command.upgrade(_alembic_cfg(), "head")
    _seed_initial_admin()


def setup(_args: argparse.Namespace) -> None:
    """Migrate the database and build the UI for a source checkout."""
    migrate(None)
    frontend_dir = _repo_dir() / "frontend"
    if frontend_dir.is_dir():
        if not (frontend_dir / "node_modules").is_dir():
            _run_pnpm(frontend_dir, "install")
        _run_pnpm(frontend_dir, "build")


def dev(_args: argparse.Namespace) -> None:
    """Start Vite, which proxies the API to this Python process."""
    import uvicorn

    from .api import create_app

    frontend_dir = _repo_dir() / "frontend"
    if not frontend_dir.is_dir():
        raise RuntimeError(f"Frontend directory does not exist: {frontend_dir}")

    if not (frontend_dir / "node_modules").is_dir():
        print("Frontend dependencies not found; installing with pnpm...", flush=True)
        _run_pnpm(frontend_dir, "install")

    # Vite proxies /api, /v1 and /v1beta to this process, so it holds the only
    # backend port; see frontend/vite.config.ts.
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(),
            host="127.0.0.1",
            port=settings.port,
            loop=_uvicorn_loop_factory_path(),
        )
    )

    def handle_signal(_signum: int, _frame: FrameType | None) -> None:
        server.should_exit = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    thread = threading.Thread(target=asyncio.run, args=(server.serve(),), daemon=True)
    thread.start()

    frontend = _pnpm_popen(
        frontend_dir,
        ["dev"],
        {
            **os.environ,
            # Vite exposes every VITE_* value to the client bundle, so only the
            # proxy target is passed; see frontend/vite.config.ts.
            "VITE_LENS_DEV_BACKEND": f"http://127.0.0.1:{settings.port}",
        },
    )

    # Keep in sync with server.port in frontend/vite.config.ts.
    print("Lens dev UI: http://127.0.0.1:3000", flush=True)

    def stop_frontend() -> None:
        if frontend.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(frontend.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return

        os.killpg(frontend.pid, signal.SIGTERM)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and frontend.poll() is None:
            time.sleep(0.1)
        if frontend.poll() is None:
            os.killpg(frontend.pid, signal.SIGKILL)

    try:
        while True:
            return_code = frontend.poll()
            if return_code is not None:
                raise SystemExit(return_code)
            time.sleep(0.25)
    finally:
        server.should_exit = True
        stop_frontend()
        thread.join(timeout=8)


def seed_admin(args: argparse.Namespace) -> None:
    """Create the initial administrator when none exists."""
    password = secrets.token_urlsafe(24) if args.generate_password else args.password
    assert isinstance(password, str)
    seed_file = Path(args.password_file) if args.password_file is not None else None
    created = _seed_initial_admin(args.username, password, password_file=seed_file)
    if not created:
        print("admin user already exists; skipped seed")
    elif args.generate_password and seed_file is None:
        print(f"generated admin password: {password}")


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments and dispatch the selected Lens command."""
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
    serve_parser.add_argument(
        "--port",
        type=int,
        default=settings.port,
        help="Listen port (default from LENS_PORT or 18080)",
    )
    serve_parser.add_argument(
        "--ui-static-dir",
        default="",
        help="Serve the built UI from this directory",
    )
    serve_parser.set_defaults(func=serve)

    dev_parser = subparsers.add_parser(
        "dev", help="Run the API and Vite development servers together"
    )
    dev_parser.set_defaults(func=dev)

    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Upgrade the database and create the admin with its initial password",
    )
    migrate_parser.set_defaults(func=migrate)

    setup_parser = subparsers.add_parser(
        "setup", help="Run migrate, then build the UI from a source checkout"
    )
    setup_parser.set_defaults(func=setup)

    seed_admin_parser = subparsers.add_parser(
        "seed-admin", help="Create an initial admin user when none exists"
    )
    seed_admin_parser.add_argument(
        "--username", default=DEFAULT_ADMIN_USERNAME, help="Admin username"
    )
    password_group = seed_admin_parser.add_mutually_exclusive_group(required=True)
    password_group.add_argument(
        "--password",
        type=_admin_password_argument,
        help="Administrator password",
    )
    password_group.add_argument(
        "--generate-password",
        action="store_true",
        help="Generate a secure random password for the initial admin",
    )
    seed_admin_parser.add_argument(
        "--password-file",
        help="Write a generated password to this file instead of standard output",
    )
    seed_admin_parser.set_defaults(func=seed_admin)

    args = parser.parse_args(argv)

    if (
        args.group == "seed-admin"
        and args.password_file is not None
        and not args.generate_password
    ):
        seed_admin_parser.error("--password-file requires --generate-password")

    if not hasattr(args, "func"):
        if args.group == "db":
            db_parser.print_help()
        else:
            parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
