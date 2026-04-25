from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

RESERVED_PREFIXES = ("api", "v1", "v1beta", "healthz", "docs", "redoc", "openapi.json")


def register(app: FastAPI, service_module) -> None:
    static_dir_value = service_module.settings.ui_static_dir.strip()
    if not static_dir_value:
        return

    static_dir = Path(static_dir_value)
    if not static_dir.is_dir():
        raise RuntimeError(f"LENS_UI_STATIC_DIR does not exist: {static_dir}")

    assets_dir = static_dir / "_next"
    if assets_dir.is_dir():
        app.mount("/_next", StaticFiles(directory=assets_dir), name="next-assets")

    _add_file_route(app, "/favicon.ico", static_dir / "favicon.ico")
    _add_file_route(app, "/logo.svg", static_dir / "logo.svg")

    brand_icons_dir = static_dir / "brand-icons"
    if brand_icons_dir.is_dir():
        app.mount("/brand-icons", StaticFiles(directory=brand_icons_dir), name="brand-icons")

    async def ui_entry(path: str = "") -> FileResponse:
        normalized = path.strip("/")
        first_segment = normalized.split("/", 1)[0] if normalized else ""
        if first_segment in RESERVED_PREFIXES:
            raise HTTPException(status_code=404, detail="Not Found")

        html_file = _resolve_html_file(static_dir, normalized)
        if html_file is None:
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(html_file)

    app.add_api_route("/", ui_entry, methods=["GET"], include_in_schema=False)
    app.add_api_route("/{path:path}", ui_entry, methods=["GET"], include_in_schema=False)


def _add_file_route(app: FastAPI, path: str, file_path: Path) -> None:
    if not file_path.is_file():
        return

    async def serve_file() -> FileResponse:
        return FileResponse(file_path)

    app.add_api_route(path, serve_file, methods=["GET"], include_in_schema=False)


def _resolve_html_file(static_dir: Path, normalized_path: str) -> Path | None:
    candidates = [static_dir / "index.html"]
    if normalized_path:
        candidates = [
            static_dir / normalized_path / "index.html",
            static_dir / f"{normalized_path}.html",
        ]

    for candidate in candidates:
        if candidate.is_file() and _is_relative_to(candidate, static_dir):
            return candidate
    return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True
