from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config import settings
from .db import Base, create_engine, create_session_factory
from .models import ErrorResponse, ProtocolKind, ProviderConfig, ProviderCreate, ProviderUpdate, RoutePreviewRequest
from .router import RoundRobinRouter
from .store import ProviderStore
from .upstreams import build_upstream_request


class AppState:
    def __init__(self) -> None:
        timeout = httpx.Timeout(
            timeout=settings.request_timeout_seconds,
            connect=settings.connect_timeout_seconds,
        )
        limits = httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_keepalive_connections,
        )
        self.http = httpx.AsyncClient(timeout=timeout, limits=limits)
        self.engine = create_engine(settings.database_url)
        self.session_factory = create_session_factory(self.engine)
        self.store = ProviderStore(self.session_factory)
        self.router = RoundRobinRouter()

    async def startup(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.http.aclose()
        await self.engine.dispose()


app_state = AppState()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await app_state.startup()
    yield
    await app_state.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/providers")
async def list_providers() -> list[ProviderConfig]:
    return await app_state.store.list()


@app.post("/api/providers", status_code=201)
async def create_provider(payload: ProviderCreate) -> ProviderConfig:
    return await app_state.store.create(payload)


@app.put("/api/providers/{provider_id}")
async def update_provider(provider_id: str, payload: ProviderUpdate) -> ProviderConfig:
    try:
        return await app_state.store.update(provider_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}") from exc


@app.delete("/api/providers/{provider_id}", status_code=204)
async def delete_provider(provider_id: str) -> Response:
    try:
        await app_state.store.delete(provider_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}") from exc
    return Response(status_code=204)


@app.get("/api/router")
async def router_snapshot() -> dict[str, Any]:
    providers = await app_state.store.list()
    return app_state.router.snapshot(providers).model_dump(mode="json")


@app.post("/api/router/preview")
async def router_preview(payload: RoutePreviewRequest) -> dict[str, Any]:
    providers = await app_state.store.list()
    return app_state.router.preview(providers, payload.protocol, payload.model).model_dump(mode="json")


@app.post("/v1/chat/completions")
async def proxy_openai_chat(request: Request):
    body = await request.json()
    return await _proxy_protocol(ProtocolKind.OPENAI_CHAT, body)


@app.post("/v1/responses")
async def proxy_openai_responses(request: Request):
    body = await request.json()
    return await _proxy_protocol(ProtocolKind.OPENAI_RESPONSES, body)


@app.post("/v1/messages")
async def proxy_anthropic_messages(request: Request):
    body = await request.json()
    return await _proxy_protocol(ProtocolKind.ANTHROPIC, body)


@app.post("/v1beta/models/{model_name}:generateContent")
async def proxy_gemini_generate_content(model_name: str, request: Request):
    body = await request.json()
    body = {**body, "model": model_name, "stream": False}
    return await _proxy_protocol(ProtocolKind.GEMINI, body)


@app.post("/v1beta/models/{model_name}:streamGenerateContent")
async def proxy_gemini_stream_generate_content(model_name: str, request: Request):
    body = await request.json()
    body = {**body, "model": model_name, "stream": True}
    return await _proxy_protocol(ProtocolKind.GEMINI, body)


async def _proxy_protocol(protocol: ProtocolKind, body: dict[str, Any]) -> Response:
    providers = await app_state.store.list()
    requested_model = _requested_model(protocol, body)
    try:
        selection = app_state.router.select(providers, protocol, requested_model)
    except LookupError as exc:
        error_body = ErrorResponse(
            error={
                "type": "routing_error",
                "message": str(exc),
            }
        )
        return JSONResponse(status_code=503, content=error_body.model_dump(mode="json"))

    errors: list[str] = []

    for provider in [selection.primary, *selection.fallbacks]:
        try:
            return await _call_provider(provider, body)
        except HTTPException as exc:
            message = f"{provider.id}: {exc.detail}"
            app_state.router.record_failure(provider.id, message)
            errors.append(message)

    error_body = ErrorResponse(
        error={
            "type": "upstream_error",
            "message": "All upstream providers failed",
            "details": errors,
        }
    )
    return JSONResponse(status_code=502, content=error_body.model_dump(mode="json"))


async def _call_provider(provider: ProviderConfig, body: dict[str, Any]) -> Response:
    upstream = build_upstream_request(provider, body, settings)
    stream = bool(body.get("stream"))

    try:
        if stream:
            request = app_state.http.build_request(
                upstream.method,
                upstream.url,
                headers=upstream.headers,
                json=upstream.json_body,
            )
            response = await app_state.http.send(request, stream=True)
            response.raise_for_status()
            app_state.router.record_success(provider.id)

            async def iterator():
                try:
                    async for chunk in response.aiter_bytes():
                        yield chunk
                finally:
                    await response.aclose()

            return StreamingResponse(
                iterator(),
                status_code=response.status_code,
                media_type=response.headers.get("content-type"),
                headers=_passthrough_headers(response.headers),
            )

        response = await app_state.http.request(
            upstream.method,
            upstream.url,
            headers=upstream.headers,
            json=upstream.json_body,
        )
        response.raise_for_status()
        app_state.router.record_success(provider.id)

        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=response.headers.get("content-type"),
            headers=_passthrough_headers(response.headers),
        )
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text or f"HTTP {exc.response.status_code}"
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Transport error: {exc}") from exc


def _passthrough_headers(headers: httpx.Headers) -> dict[str, str]:
    allowed = {}
    for key in (
        "content-type",
        "cache-control",
        "x-request-id",
        "anthropic-request-id",
        "x-goog-request-id",
    ):
        if key in headers:
            allowed[key] = headers[key]
    return allowed


def _requested_model(protocol: ProtocolKind, body: dict[str, Any]) -> str | None:
    if protocol == ProtocolKind.GEMINI:
        return body.get("model")
    return body.get("model")
