from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .admin_store import AdminStore
from .auth import create_access_token, decode_access_token
from .config import settings
from .db import Base, create_engine, create_session_factory
from .domain_store import DomainStore
from .models import AdminLoginRequest, AdminProfile, AuthTokenResponse, ErrorResponse, GatewayKey, GatewayKeyCreate, GatewayKeyUpdate, ModelGroup, ModelGroupCreate, ModelGroupUpdate, ProtocolKind, ProviderConfig, ProviderCreate, ProviderUpdate, RoutePreviewRequest, RoutingStrategy, SettingItem, SettingsUpdate
from .router import RoundRobinRouter
from .store import ProviderStore
from .upstreams import build_upstream_request


class AppState:
    def __init__(self) -> None:
        self.http = self._create_http_client()
        self.engine = create_engine(settings.database_url)
        self.session_factory = create_session_factory(self.engine)
        self.admin_store = AdminStore(self.session_factory)
        self.domain_store = DomainStore(self.session_factory)
        self.store = ProviderStore(self.session_factory)
        self.router = RoundRobinRouter()

    @staticmethod
    def _create_http_client() -> httpx.AsyncClient:
        timeout = httpx.Timeout(
            timeout=settings.request_timeout_seconds,
            connect=settings.connect_timeout_seconds,
        )
        limits = httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_keepalive_connections,
        )
        return httpx.AsyncClient(timeout=timeout, limits=limits)


@dataclass
class RoutingPlan:
    requested_model: str | None
    matched_group: ModelGroup | None
    strategy: RoutingStrategy
    allowed_provider_ids: set[str] | None
    use_model_matching: bool


async def _startup_app_state(state: AppState) -> None:
    if state.http.is_closed:
        state.http = state._create_http_client()

    async with state.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await state.admin_store.ensure_default_admin(
        settings.admin_default_username,
        settings.admin_default_password,
    )


async def _close_app_state(state: AppState) -> None:
    if not state.http.is_closed:
        await state.http.aclose()
    await state.engine.dispose()


app_state = AppState()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await _startup_app_state(app_state)
    yield
    await _close_app_state(app_state)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
auth_scheme = HTTPBearer(auto_error=False)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
):
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials, settings)
        username = payload.get("sub")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    admin = await app_state.admin_store.get_by_username(username)
    if admin is None or admin.is_active != 1:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found")

    return admin


async def get_current_gateway_key(request: Request) -> GatewayKey:
    authorization = request.headers.get("authorization", "")
    x_api_key = request.headers.get("x-api-key", "")
    x_goog_api_key = request.headers.get("x-goog-api-key", "")

    secret = ""
    if authorization.lower().startswith("bearer "):
        secret = authorization[7:].strip()
    elif x_api_key:
        secret = x_api_key.strip()
    elif x_goog_api_key:
        secret = x_goog_api_key.strip()

    if not secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing gateway API key")

    gateway_key = await app_state.domain_store.get_gateway_key_by_secret(secret)
    if gateway_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid gateway API key")

    return gateway_key


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=AuthTokenResponse)
async def login(payload: AdminLoginRequest) -> AuthTokenResponse:
    user = await app_state.admin_store.authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token, expires_in = create_access_token(user.username, settings)
    return AuthTokenResponse(access_token=access_token, expires_in=expires_in)


@app.get("/api/auth/me", response_model=AdminProfile)
async def current_admin(admin = Depends(get_current_admin)) -> AdminProfile:
    return AdminProfile(id=admin.id, username=admin.username)


@app.get("/api/providers")
async def list_providers(_: Any = Depends(get_current_admin)) -> list[ProviderConfig]:
    return await app_state.store.list()


@app.post("/api/providers", status_code=201)
async def create_provider(payload: ProviderCreate, _: Any = Depends(get_current_admin)) -> ProviderConfig:
    return await app_state.store.create(payload)


@app.put("/api/providers/{provider_id}")
async def update_provider(provider_id: str, payload: ProviderUpdate, _: Any = Depends(get_current_admin)) -> ProviderConfig:
    try:
        return await app_state.store.update(provider_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}") from exc


@app.delete("/api/providers/{provider_id}", status_code=204)
async def delete_provider(provider_id: str, _: Any = Depends(get_current_admin)) -> Response:
    try:
        await app_state.store.delete(provider_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}") from exc
    return Response(status_code=204)


@app.get("/api/router")
async def router_snapshot(_: Any = Depends(get_current_admin)) -> dict[str, Any]:
    providers = await app_state.store.list()
    return app_state.router.snapshot(providers).model_dump(mode="json")


@app.post("/api/router/preview")
async def router_preview(payload: RoutePreviewRequest, _: Any = Depends(get_current_admin)) -> dict[str, Any]:
    providers = await app_state.store.list()
    plan = await _resolve_routing_plan(payload.protocol, payload.model)
    return app_state.router.preview(
        providers,
        payload.protocol,
        payload.model,
        strategy=plan.strategy,
        allowed_provider_ids=plan.allowed_provider_ids,
        use_model_matching=plan.use_model_matching,
        matched_group_name=plan.matched_group.name if plan.matched_group else None,
    ).model_dump(mode="json")


@app.get("/api/model-groups", response_model=list[ModelGroup])
async def list_model_groups(_: Any = Depends(get_current_admin)) -> list[ModelGroup]:
    return await app_state.domain_store.list_groups()


@app.post("/api/model-groups", response_model=ModelGroup, status_code=201)
async def create_model_group(payload: ModelGroupCreate, _: Any = Depends(get_current_admin)) -> ModelGroup:
    return await app_state.domain_store.create_group(payload)


@app.put("/api/model-groups/{group_id}", response_model=ModelGroup)
async def update_model_group(group_id: str, payload: ModelGroupUpdate, _: Any = Depends(get_current_admin)) -> ModelGroup:
    try:
        return await app_state.domain_store.update_group(group_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Model group not found: {group_id}") from exc


@app.delete("/api/model-groups/{group_id}", status_code=204)
async def delete_model_group(group_id: str, _: Any = Depends(get_current_admin)) -> Response:
    try:
        await app_state.domain_store.delete_group(group_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Model group not found: {group_id}") from exc
    return Response(status_code=204)


@app.get("/api/gateway-keys", response_model=list[GatewayKey])
async def list_gateway_keys(_: Any = Depends(get_current_admin)) -> list[GatewayKey]:
    return await app_state.domain_store.list_gateway_keys()


@app.post("/api/gateway-keys", response_model=GatewayKey, status_code=201)
async def create_gateway_key(payload: GatewayKeyCreate, _: Any = Depends(get_current_admin)) -> GatewayKey:
    return await app_state.domain_store.create_gateway_key(payload)


@app.put("/api/gateway-keys/{key_id}", response_model=GatewayKey)
async def update_gateway_key(key_id: str, payload: GatewayKeyUpdate, _: Any = Depends(get_current_admin)) -> GatewayKey:
    try:
        return await app_state.domain_store.update_gateway_key(key_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Gateway key not found: {key_id}") from exc


@app.delete("/api/gateway-keys/{key_id}", status_code=204)
async def delete_gateway_key(key_id: str, _: Any = Depends(get_current_admin)) -> Response:
    try:
        await app_state.domain_store.delete_gateway_key(key_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Gateway key not found: {key_id}") from exc
    return Response(status_code=204)


@app.get("/api/settings", response_model=list[SettingItem])
async def list_settings(_: Any = Depends(get_current_admin)) -> list[SettingItem]:
    return await app_state.domain_store.list_settings()


@app.put("/api/settings", response_model=list[SettingItem])
async def update_settings(payload: SettingsUpdate, _: Any = Depends(get_current_admin)) -> list[SettingItem]:
    return await app_state.domain_store.upsert_settings(payload.items)


@app.post("/v1/chat/completions")
async def proxy_openai_chat(request: Request, _: GatewayKey = Depends(get_current_gateway_key)):
    body = await request.json()
    return await _proxy_protocol(ProtocolKind.OPENAI_CHAT, body)


@app.post("/v1/responses")
async def proxy_openai_responses(request: Request, _: GatewayKey = Depends(get_current_gateway_key)):
    body = await request.json()
    return await _proxy_protocol(ProtocolKind.OPENAI_RESPONSES, body)


@app.post("/v1/messages")
async def proxy_anthropic_messages(request: Request, _: GatewayKey = Depends(get_current_gateway_key)):
    body = await request.json()
    return await _proxy_protocol(ProtocolKind.ANTHROPIC, body)


@app.post("/v1beta/models/{model_name}:generateContent")
async def proxy_gemini_generate_content(model_name: str, request: Request, _: GatewayKey = Depends(get_current_gateway_key)):
    body = await request.json()
    body = {**body, "model": model_name, "stream": False}
    return await _proxy_protocol(ProtocolKind.GEMINI, body)


@app.post("/v1beta/models/{model_name}:streamGenerateContent")
async def proxy_gemini_stream_generate_content(model_name: str, request: Request, _: GatewayKey = Depends(get_current_gateway_key)):
    body = await request.json()
    body = {**body, "model": model_name, "stream": True}
    return await _proxy_protocol(ProtocolKind.GEMINI, body)


async def _proxy_protocol(protocol: ProtocolKind, body: dict[str, Any]) -> Response:
    providers = await app_state.store.list()
    plan = await _resolve_routing_plan(protocol, _requested_model(protocol, body))
    try:
        selection = app_state.router.select(
            providers,
            protocol,
            plan.requested_model,
            strategy=plan.strategy,
            allowed_provider_ids=plan.allowed_provider_ids,
            use_model_matching=plan.use_model_matching,
        )
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


async def _resolve_routing_plan(protocol: ProtocolKind, requested_model: str | None) -> RoutingPlan:
    matched_group = await app_state.domain_store.find_group_by_name(protocol.value, requested_model)
    if matched_group is not None:
        return RoutingPlan(
            requested_model=requested_model,
            matched_group=matched_group,
            strategy=matched_group.strategy,
            allowed_provider_ids=set(matched_group.provider_ids),
            use_model_matching=False,
        )

    return RoutingPlan(
        requested_model=requested_model,
        matched_group=None,
        strategy=RoutingStrategy.WEIGHTED,
        allowed_provider_ids=None,
        use_model_matching=True,
    )
