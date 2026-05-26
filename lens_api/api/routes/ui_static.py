from pathlib import Path
from types import ModuleType

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from starlette.staticfiles import StaticFiles

RESERVED_PREFIXES = ("api", "v1", "v1beta", "healthz", "docs", "redoc", "openapi.json")


def register(app: FastAPI, service_module: ModuleType) -> None:
    static_dir_value = service_module.settings.ui_static_dir.strip()
    if not static_dir_value:
        return

    static_dir = Path(static_dir_value)
    if not static_dir.is_dir():
        raise RuntimeError(f"LENS_UI_STATIC_DIR does not exist: {static_dir}")
    static_root = static_dir.resolve()

    assets_dir = static_dir / "_next"
    if assets_dir.is_dir():
        app.mount("/_next", StaticFiles(directory=assets_dir), name="next-assets")

    _add_file_route(app, "/favicon.ico", static_dir / "favicon.ico")
    _add_file_route(app, "/logo.svg", static_dir / "logo.svg")

    brand_icons_dir = static_dir / "brand-icons"
    if brand_icons_dir.is_dir():
        app.mount(
            "/brand-icons", StaticFiles(directory=brand_icons_dir), name="brand-icons"
        )

    async def ui_entry(path: str = "") -> FileResponse:
        return await run_in_threadpool(_resolve_ui_entry, static_dir, static_root, path)

    app.add_api_route("/", ui_entry, methods=["GET", "HEAD"], include_in_schema=False)
    app.add_api_route(
        "/{path:path}", ui_entry, methods=["GET", "HEAD"], include_in_schema=False
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
    normalized = path.strip("/")
    first_segment = normalized.split("/", 1)[0] if normalized else ""
    if first_segment in RESERVED_PREFIXES:
        raise HTTPException(status_code=404, detail="Not Found")

    if normalized:
        for candidate in _next_rsc_candidates(static_dir, normalized):
            if candidate.is_file() and candidate.resolve().is_relative_to(static_root):
                return FileResponse(candidate)
        html_candidates = [
            static_dir / normalized / "index.html",
            static_dir / f"{normalized}.html",
        ]
    else:
        html_candidates = [static_dir / "index.html"]

    for candidate in html_candidates:
        if candidate.is_file() and candidate.resolve().is_relative_to(static_root):
            return FileResponse(candidate)
    raise HTTPException(status_code=404, detail="Not Found")


def _next_rsc_candidates(static_dir: Path, normalized_path: str) -> list[Path]:
    parts = Path(normalized_path).parts
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
            candidates.append(static_dir / normalized_path)
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
