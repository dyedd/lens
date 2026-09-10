from pathlib import Path

from fastapi import FastAPI, HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

RESERVED_PREFIXES = ("api", "v1", "v1beta", "docs", "redoc", "openapi.json")
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
_IMMUTABLE_ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"


class _ImmutableStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code in (200, 304):
            response.headers["Cache-Control"] = _IMMUTABLE_ASSET_CACHE_CONTROL
        return response


def register(app: FastAPI, static_dir_value: str = "") -> None:
    """Serve the built UI from the default or explicitly configured directory."""
    static_dir_value = static_dir_value.strip()
    if not static_dir_value:
        _register_vite_bundle(app, FRONTEND_DIR)
        return

    static_dir = Path(static_dir_value)
    if not static_dir.is_dir():
        raise RuntimeError(f"UI static directory does not exist: {static_dir}")
    _register_custom_bundle(app, static_dir)


def _register_vite_bundle(app: FastAPI, static_dir: Path) -> None:
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            _ImmutableStaticFiles(directory=assets_dir),
            name="frontend-assets",
        )
    if static_dir.is_dir():
        app.frontend("/", directory=static_dir, check_dir=False)


def _register_custom_bundle(app: FastAPI, static_dir: Path) -> None:
    static_root = static_dir.resolve()
    assets_dir = static_dir / "_next" / "static"
    if assets_dir.is_dir():
        app.mount(
            "/_next/static",
            _ImmutableStaticFiles(directory=assets_dir),
            name="next-assets",
        )

    _add_file_route(app, "/favicon.ico", static_dir / "favicon.ico")
    _add_file_route(app, "/logo.svg", static_dir / "logo.svg")

    brand_icons_dir = static_dir / "brand-icons"
    if brand_icons_dir.is_dir():
        app.mount(
            "/brand-icons", StaticFiles(directory=brand_icons_dir), name="brand-icons"
        )

    async def serve_ui_entry(path: str = "") -> FileResponse:
        return await run_in_threadpool(_resolve_ui_entry, static_dir, static_root, path)

    app.add_api_route(
        "/", serve_ui_entry, methods=["GET", "HEAD"], include_in_schema=False
    )
    app.add_api_route(
        "/{path:path}", serve_ui_entry, methods=["GET", "HEAD"], include_in_schema=False
    )


def _add_file_route(app: FastAPI, path: str, file_path: Path) -> None:
    if not file_path.is_file():
        return

    async def serve_file() -> FileResponse:
        return await run_in_threadpool(FileResponse, file_path)

    app.add_api_route(
        path, serve_file, methods=["GET", "HEAD"], include_in_schema=False
    )


def _resolve_ui_entry(static_dir: Path, static_root: Path, path: str) -> FileResponse:
    route_path = path.strip("/")
    first_segment = route_path.split("/", 1)[0] if route_path else ""
    if first_segment in RESERVED_PREFIXES:
        raise HTTPException(status_code=404, detail="Not Found")

    if route_path:
        direct_file = static_dir / route_path
        if direct_file.is_file() and direct_file.resolve().is_relative_to(static_root):
            return FileResponse(direct_file)
        for candidate in _rsc_candidates(static_dir, route_path):
            if candidate.is_file() and candidate.resolve().is_relative_to(static_root):
                return FileResponse(candidate)
        html_candidates = [
            static_dir / route_path / "index.html",
            static_dir / f"{route_path}.html",
        ]
    else:
        html_candidates = [static_dir / "index.html"]

    for candidate in html_candidates:
        if candidate.is_file() and candidate.resolve().is_relative_to(static_root):
            return FileResponse(candidate)
    raise HTTPException(status_code=404, detail="Not Found")


def _rsc_candidates(static_dir: Path, route_path: str) -> list[Path]:
    parts = Path(route_path).parts
    candidates: list[Path] = []
    for index, part in enumerate(parts):
        for prefix in ("__next", "_next"):
            marker = f"{prefix}."
            if not part.startswith(marker):
                continue
            rest = part.removeprefix(marker)
            rest_parts = rest.split(".")
            if len(rest_parts) < 2 or rest_parts[-1] != "txt":
                continue
            candidates.append(static_dir / route_path)
            leaf = f"{rest_parts[-2]}.txt"
            mapped_parts = (
                *parts[:index],
                prefix,
                *rest_parts[:-2],
                leaf,
                *parts[index + 1 :],
            )
            candidates.append(static_dir.joinpath(*mapped_parts))
            alternate_prefix = "__next" if prefix == "_next" else "_next"
            alternate_parts = (
                *parts[:index],
                alternate_prefix,
                *rest_parts[:-2],
                leaf,
                *parts[index + 1 :],
            )
            candidates.append(static_dir.joinpath(*alternate_parts))
    return candidates
