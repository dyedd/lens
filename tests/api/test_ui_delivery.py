from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

import lens_api.api.app as app_module
from lens_api.api.routes import ui_static


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


async def _cors_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    response.headers["vary"] = "Origin"
    return response


def _create_test_app(monkeypatch: pytest.MonkeyPatch, static_dir: str) -> FastAPI:
    def include_test_routes(
        app: FastAPI, _service: object, *, ui_static_dir: str = ""
    ) -> None:
        @app.get("/large")
        async def large_response() -> Response:
            return Response(b"x" * 4096, media_type="text/plain")

        @app.get("/events")
        async def event_stream() -> StreamingResponse:
            return StreamingResponse(
                iter([b"data: ready\n\n"]), media_type="text/event-stream"
            )

        ui_static.register(app, ui_static_dir)

    monkeypatch.setattr(app_module, "include_routes", include_test_routes)
    service = SimpleNamespace(
        lifespan=_lifespan,
        dynamic_cors_middleware=_cors_middleware,
        register_exception_handlers=lambda _app: None,
    )
    return app_module.create_app(service, ui_static_dir=static_dir)


def test_app_compresses_large_responses_but_not_event_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _create_test_app(monkeypatch, "")

    with TestClient(app) as client:
        compressed = client.get("/large", headers={"Accept-Encoding": "gzip"})
        event_stream = client.get("/events", headers={"Accept-Encoding": "gzip"})

    assert compressed.status_code == 200
    assert compressed.content == b"x" * 4096
    assert compressed.headers["content-encoding"] == "gzip"
    assert set(compressed.headers["vary"].split(", ")) == {
        "Accept-Encoding",
        "Origin",
    }
    assert event_stream.status_code == 200
    assert "content-encoding" not in event_stream.headers


def test_next_static_assets_are_compressed_and_cached_immutably(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    static_dir = tmp_path / "ui"
    asset_dir = static_dir / "_next" / "static" / "chunks"
    asset_dir.mkdir(parents=True)
    asset = b"const value = 'lens';\n" * 256
    (asset_dir / "app-123.js").write_bytes(asset)
    (static_dir / "index.html").write_text("<main>Lens</main>", encoding="utf-8")
    app = _create_test_app(monkeypatch, str(static_dir))

    with TestClient(app) as client:
        compressed = client.get(
            "/_next/static/chunks/app-123.js",
            headers={"Accept-Encoding": "gzip"},
        )
        identity = client.get(
            "/_next/static/chunks/app-123.js",
            headers={"Accept-Encoding": "identity"},
        )
        revalidated = client.get(
            "/_next/static/chunks/app-123.js",
            headers={
                "Accept-Encoding": "identity",
                "If-None-Match": identity.headers["etag"],
            },
        )
        html = client.get("/", headers={"Accept-Encoding": "identity"})
        missing = client.get(
            "/_next/static/chunks/missing.js",
            headers={"Accept-Encoding": "identity"},
        )

    cache_control = "public, max-age=31536000, immutable"
    assert compressed.status_code == 200
    assert compressed.content == asset
    assert compressed.headers["content-encoding"] == "gzip"
    assert compressed.headers["cache-control"] == cache_control
    assert identity.status_code == 200
    assert "content-encoding" not in identity.headers
    assert identity.headers["cache-control"] == cache_control
    assert revalidated.status_code == 304
    assert revalidated.headers["cache-control"] == cache_control
    assert html.status_code == 200
    assert "cache-control" not in html.headers
    assert missing.status_code == 404
    assert "cache-control" not in missing.headers
