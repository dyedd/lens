from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter
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
from .models import AdminLoginRequest, AdminProfile, AuthTokenResponse, ErrorResponse, ModelGroup, ModelGroupCreate, ModelGroupUpdate, OverviewDailyPoint, OverviewMetrics, OverviewModelAnalytics, OverviewSummary, ProtocolKind, ProviderConfig, ProviderCreate, ProviderUpdate, RequestLogItem, RoutePreviewRequest, RoutingStrategy, SettingItem, SettingsUpdate
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


@dataclass
class UpstreamResult:
    response: Response
    status_code: int
    resolved_model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0


async def _startup_app_state(state: AppState) -> None:
    if state.http.is_closed:
        state.http = state._create_http_client()

    async with state.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await state.domain_store.ensure_schema()
    await state.admin_store.ensure_default_admin(
        settings.admin_default_username,
        settings.admin_default_password,
    )
    await _bootstrap_imported_stats(state)


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


async def get_current_gateway_key(request: Request) -> str:
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

    gateway_auth = await app_state.domain_store.get_gateway_auth_config()
    if not gateway_auth["require_api_key"]:
        return secret or "anonymous"

    if not secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing gateway API key")

    if secret not in gateway_auth["keys"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid gateway API key")

    return secret


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


@app.get("/api/overview", response_model=OverviewMetrics)
async def overview_metrics(_: Any = Depends(get_current_admin)) -> OverviewMetrics:
    metrics = await app_state.domain_store.get_overview_metrics()
    providers = await app_state.store.list()
    return metrics.model_copy(update={"enabled_providers": sum(1 for item in providers if item.status.value == "enabled")})


@app.get("/api/overview/summary", response_model=OverviewSummary)
async def overview_summary(_: Any = Depends(get_current_admin)) -> OverviewSummary:
    return await app_state.domain_store.get_overview_summary()


@app.get("/api/overview/daily", response_model=list[OverviewDailyPoint])
async def overview_daily(_: Any = Depends(get_current_admin)) -> list[OverviewDailyPoint]:
    return await app_state.domain_store.list_overview_daily()


@app.get("/api/overview/models", response_model=OverviewModelAnalytics)
async def overview_models(_: Any = Depends(get_current_admin)) -> OverviewModelAnalytics:
    return await app_state.domain_store.get_model_analytics()


@app.get("/api/request-logs", response_model=list[RequestLogItem])
async def request_logs(_: Any = Depends(get_current_admin)) -> list[RequestLogItem]:
    return await app_state.domain_store.list_request_logs()


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


@app.get("/api/settings", response_model=list[SettingItem])
async def list_settings(_: Any = Depends(get_current_admin)) -> list[SettingItem]:
    return await app_state.domain_store.list_settings()


@app.put("/api/settings", response_model=list[SettingItem])
async def update_settings(payload: SettingsUpdate, _: Any = Depends(get_current_admin)) -> list[SettingItem]:
    return await app_state.domain_store.upsert_settings(payload.items)


@app.post("/v1/chat/completions")
async def proxy_openai_chat(request: Request, gateway_key: str = Depends(get_current_gateway_key)):
    body = await request.json()
    return await _proxy_protocol(ProtocolKind.OPENAI_CHAT, body, gateway_key)


@app.post("/v1/responses")
async def proxy_openai_responses(request: Request, gateway_key: str = Depends(get_current_gateway_key)):
    body = await request.json()
    return await _proxy_protocol(ProtocolKind.OPENAI_RESPONSES, body, gateway_key)


@app.post("/v1/messages")
async def proxy_anthropic_messages(request: Request, gateway_key: str = Depends(get_current_gateway_key)):
    body = await request.json()
    return await _proxy_protocol(ProtocolKind.ANTHROPIC, body, gateway_key)


@app.post("/v1beta/models/{model_name}:generateContent")
async def proxy_gemini_generate_content(model_name: str, request: Request, gateway_key: str = Depends(get_current_gateway_key)):
    body = await request.json()
    body = {**body, "model": model_name, "stream": False}
    return await _proxy_protocol(ProtocolKind.GEMINI, body, gateway_key)


@app.post("/v1beta/models/{model_name}:streamGenerateContent")
async def proxy_gemini_stream_generate_content(model_name: str, request: Request, gateway_key: str = Depends(get_current_gateway_key)):
    body = await request.json()
    body = {**body, "model": model_name, "stream": True}
    return await _proxy_protocol(ProtocolKind.GEMINI, body, gateway_key)


async def _proxy_protocol(protocol: ProtocolKind, body: dict[str, Any], gateway_key: str) -> Response:
    providers = await app_state.store.list()
    plan = await _resolve_routing_plan(protocol, _requested_model(protocol, body))
    started_at = perf_counter()
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
        await _record_request_log(
            protocol=protocol,
            requested_model=plan.requested_model,
            matched_group_name=plan.matched_group.name if plan.matched_group else None,
            provider_id=None,
            gateway_key=gateway_key,
            status_code=503,
            success=False,
            latency_ms=_elapsed_ms(started_at),
            error_message=str(exc),
        )
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
            result = await _call_provider(provider, body)
            await _record_request_log(
                protocol=protocol,
                requested_model=plan.requested_model,
                matched_group_name=plan.matched_group.name if plan.matched_group else None,
                provider_id=provider.id,
                gateway_key=gateway_key,
                status_code=result.status_code,
                success=True,
                latency_ms=_elapsed_ms(started_at),
                resolved_model=result.resolved_model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                input_cost_usd=result.input_cost_usd,
                output_cost_usd=result.output_cost_usd,
                total_cost_usd=result.total_cost_usd,
                error_message=None,
            )
            return result.response
        except HTTPException as exc:
            message = f"{provider.id}: {exc.detail}"
            app_state.router.record_failure(provider.id, message)
            errors.append(message)
            await _record_request_log(
                protocol=protocol,
                requested_model=plan.requested_model,
                matched_group_name=plan.matched_group.name if plan.matched_group else None,
                provider_id=provider.id,
                gateway_key=gateway_key,
                status_code=exc.status_code,
                success=False,
                latency_ms=_elapsed_ms(started_at),
                error_message=message,
            )

    error_body = ErrorResponse(
        error={
            "type": "upstream_error",
            "message": "All upstream providers failed",
            "details": errors,
        }
    )
    return JSONResponse(status_code=502, content=error_body.model_dump(mode="json"))


async def _call_provider(provider: ProviderConfig, body: dict[str, Any]) -> UpstreamResult:
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

            return UpstreamResult(
                response=StreamingResponse(
                    iterator(),
                    status_code=response.status_code,
                    media_type=response.headers.get("content-type"),
                    headers=_passthrough_headers(response.headers),
                ),
                status_code=response.status_code,
                resolved_model=provider.model_name or body.get("model"),
            )

        response = await app_state.http.request(
            upstream.method,
            upstream.url,
            headers=upstream.headers,
            json=upstream.json_body,
        )
        response.raise_for_status()
        app_state.router.record_success(provider.id)

        parsed = _extract_response_usage(provider.protocol, response)
        input_cost_usd, output_cost_usd, total_cost_usd = await app_state.domain_store.estimate_model_cost(
            parsed["resolved_model"],
            parsed["input_tokens"],
            parsed["output_tokens"],
        )

        return UpstreamResult(
            response=Response(
                content=response.content,
                status_code=response.status_code,
                media_type=response.headers.get("content-type"),
                headers=_passthrough_headers(response.headers),
            ),
            status_code=response.status_code,
            resolved_model=parsed["resolved_model"],
            input_tokens=parsed["input_tokens"],
            output_tokens=parsed["output_tokens"],
            total_tokens=parsed["total_tokens"],
            input_cost_usd=input_cost_usd,
            output_cost_usd=output_cost_usd,
            total_cost_usd=total_cost_usd,
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


def _elapsed_ms(started_at: float) -> int:
    return max(int((perf_counter() - started_at) * 1000), 0)


async def _record_request_log(
    *,
    protocol: ProtocolKind,
    requested_model: str | None,
    matched_group_name: str | None,
    provider_id: str | None,
    gateway_key: str,
    status_code: int,
    success: bool,
    latency_ms: int,
    resolved_model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    input_cost_usd: float = 0.0,
    output_cost_usd: float = 0.0,
    total_cost_usd: float = 0.0,
    error_message: str | None,
) -> None:
    await app_state.domain_store.create_request_log(
        protocol=protocol.value,
        requested_model=requested_model,
        matched_group_name=matched_group_name,
        provider_id=provider_id,
        gateway_key_id=gateway_key,
        status_code=status_code,
        success=success,
        latency_ms=latency_ms,
        resolved_model=resolved_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_cost_usd=input_cost_usd,
        output_cost_usd=output_cost_usd,
        total_cost_usd=total_cost_usd,
        error_message=error_message,
    )


def _extract_response_usage(protocol: ProtocolKind, response: httpx.Response) -> dict[str, int | str | None]:
    payload = response.json()

    if protocol == ProtocolKind.OPENAI_CHAT:
        usage = payload.get("usage") or {}
        return {
            "resolved_model": payload.get("model"),
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }

    if protocol == ProtocolKind.OPENAI_RESPONSES:
        usage = payload.get("usage") or {}
        return {
            "resolved_model": payload.get("model"),
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }

    if protocol == ProtocolKind.ANTHROPIC:
        usage = payload.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        return {
            "resolved_model": payload.get("model"),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

    usage = payload.get("usageMetadata") or {}
    input_tokens = int(usage.get("promptTokenCount") or usage.get("inputTokenCount") or 0)
    output_tokens = int(usage.get("candidatesTokenCount") or usage.get("outputTokenCount") or 0)
    total_tokens = int(usage.get("totalTokenCount") or (input_tokens + output_tokens))
    return {
        "resolved_model": payload.get("modelVersion") or payload.get("model"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


async def _bootstrap_imported_stats(state: AppState) -> None:
    default_export = Path(r"D:\dyedd\Downloads\octopus-export-20260330203705.json")
    if not default_export.exists():
        return

    try:
        payload = json.loads(default_export.read_text(encoding="utf-8"))
        await state.domain_store.replace_imported_stats(
            total=payload.get("stats_total"),
            daily=payload.get("stats_daily", []),
            model_prices=[
                {
                    "model_key": item.get("name"),
                    "display_name": item.get("name"),
                    "input_price_per_million": item.get("input"),
                    "output_price_per_million": item.get("output"),
                }
                for item in payload.get("llm_infos", [])
                if item.get("name")
            ],
        )
    except Exception:
        return
