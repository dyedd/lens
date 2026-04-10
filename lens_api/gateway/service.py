from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
import json
from pathlib import Path
from time import perf_counter
from typing import Any
from copy import deepcopy

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from ..core.auth import create_access_token, decode_access_token
from ..core.config import settings
from ..core.db import create_engine, create_session_factory
from ..core.model_prices import build_group_price_payloads, build_models_dev_price_index
from ..models import AdminLoginRequest, AdminPasswordChangeRequest, AdminProfile, AppInfo, AuthTokenResponse, ErrorResponse, ModelGroup, ModelGroupCandidatesRequest, ModelGroupCandidatesResponse, ModelGroupCreate, ModelGroupStats, ModelGroupUpdate, ModelPriceItem, ModelPriceListResponse, ModelPriceUpdate, OverviewDailyPoint, OverviewMetrics, OverviewModelAnalytics, OverviewSummary, ProtocolKind, PublicBranding, ChannelConfig, RequestLogDetail, RequestLogItem, RoutePreviewRequest, RoutingStrategy, SettingItem, SettingsUpdate, SiteConfig, SiteCreate, SiteModelFetchItem, SiteModelFetchRequest, SiteUpdate
from ..persistence.admin_store import AdminStore
from ..persistence.domain_store import DomainStore, SETTING_GATEWAY_API_KEY_HINT, SETTING_GATEWAY_API_KEYS, SETTING_SITE_LOGO_URL, SETTING_SITE_NAME
from ..persistence.channel_store import ChannelStore
from ..api import create_app
from .router import RoundRobinRouter, RouteTarget
from .upstreams import build_upstream_request, resolve_channel_api_key, resolve_channel_base_url, resolve_upstream_proxy_url
from .. import __version__ as backend_version


@lru_cache(maxsize=1)
def _read_frontend_version() -> str:
    package_file = Path(__file__).resolve().parents[2] / "ui" / "package.json"
    try:
        payload = json.loads(package_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "0.1.0"
    version = str(payload.get("version") or "").strip()
    return version or "0.1.0"


class AppState:
    def __init__(self) -> None:
        self.http = self._create_http_client()
        self.engine = create_engine(settings.database_url)
        self.session_factory = create_session_factory(self.engine)
        self.admin_store = AdminStore(self.session_factory)
        self.domain_store = DomainStore(self.session_factory)
        self.store = ChannelStore(self.session_factory)
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
    route_targets: list[RouteTarget] | None
    use_model_matching: bool
    cursor_key: str | None = None


@dataclass
class UpstreamResult:
    response: Response
    status_code: int
    is_stream: bool = False
    first_token_latency_ms: int = 0
    resolved_model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    request_content: str | None = None
    response_content: str | None = None
    stream_capture: StreamCapture | None = None


@dataclass
class AttemptLog:
    channel_id: str
    channel_name: str
    model_name: str | None
    status_code: int | None
    success: bool
    duration_ms: int
    error_message: str | None = None


@dataclass
class StreamCapture:
    saw_first_chunk: bool = False
    first_token_latency_ms: int = 0
    response_content: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    resolved_model: str | None = None
    errors: list[str] = field(default_factory=list)


async def _startup_app_state(state: AppState) -> None:
    if state.http.is_closed:
        state.http = state._create_http_client()


async def _close_app_state(state: AppState) -> None:
    if not state.http.is_closed:
        await state.http.aclose()
    await state.engine.dispose()


app_state = AppState()


@asynccontextmanager
async def _managed_lifespan(state: AppState):
    await _startup_app_state(state)
    try:
        yield
    except asyncio.CancelledError:
        # Uvicorn on Windows can cancel the lifespan receive loop during Ctrl+C.
        # Treat it as normal shutdown so the console does not dump an extra traceback.
        pass
    finally:
        await _close_app_state(state)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with _managed_lifespan(app_state):
        yield


auth_scheme = HTTPBearer(auto_error=False)


async def dynamic_cors_middleware(request: Request, call_next):
    response = await call_next(request)
    runtime = await app_state.domain_store.get_runtime_settings()
    allow_origins = runtime["cors_allow_origins"]
    origin = request.headers.get("origin", "")
    if allow_origins == ["*"]:
        response.headers["access-control-allow-origin"] = "*"
    elif origin and origin in allow_origins:
        response.headers["access-control-allow-origin"] = origin
        response.headers["vary"] = "Origin"
    response.headers["access-control-allow-credentials"] = "true"
    response.headers["access-control-allow-methods"] = "*"
    response.headers["access-control-allow-headers"] = "*"
    return response


async def cors_preflight(path: str, request: Request) -> Response:
    runtime = await app_state.domain_store.get_runtime_settings()
    allow_origins = runtime["cors_allow_origins"]
    origin = request.headers.get("origin", "")
    headers = {
        "access-control-allow-credentials": "true",
        "access-control-allow-methods": "*",
        "access-control-allow-headers": request.headers.get("access-control-request-headers", "*"),
    }
    if allow_origins == ["*"]:
        headers["access-control-allow-origin"] = "*"
    elif origin and origin in allow_origins:
        headers["access-control-allow-origin"] = origin
        headers["vary"] = "Origin"
    return Response(status_code=204, headers=headers)


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


async def healthz() -> dict[str, str]:
    return {"status": "ok"}


async def public_branding() -> PublicBranding:
    branding = await app_state.domain_store.get_branding_settings()
    return PublicBranding(site_name=branding["site_name"], logo_url=branding["site_logo_url"])


async def app_info(_: Any = Depends(get_current_admin)) -> AppInfo:
    branding = await app_state.domain_store.get_branding_settings()
    return AppInfo(
        backend_version=backend_version,
        frontend_version=_read_frontend_version(),
        app_env=settings.app_env,
        site_name=branding["site_name"],
        logo_url=branding["site_logo_url"],
    )


async def login(payload: AdminLoginRequest) -> AuthTokenResponse:
    user = await app_state.admin_store.authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token, expires_in = create_access_token(user.username, settings)
    return AuthTokenResponse(access_token=access_token, expires_in=expires_in)


async def current_admin(admin = Depends(get_current_admin)) -> AdminProfile:
    return AdminProfile(id=admin.id, username=admin.username)


async def change_password(payload: AdminPasswordChangeRequest, admin = Depends(get_current_admin)) -> Response:
    try:
        await app_state.admin_store.update_password(admin.username, payload.current_password, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


async def list_sites(_: Any = Depends(get_current_admin)) -> list[SiteConfig]:
    return await app_state.store.list_sites()


async def create_site(payload: SiteCreate, _: Any = Depends(get_current_admin)) -> SiteConfig:
    return await app_state.store.create_site(payload)


async def update_site(site_id: str, payload: SiteUpdate, _: Any = Depends(get_current_admin)) -> SiteConfig:
    try:
        return await app_state.store.update_site(site_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Site not found: {site_id}") from exc


async def delete_site(site_id: str, _: Any = Depends(get_current_admin)) -> Response:
    try:
        await app_state.store.delete_site(site_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Site not found: {site_id}") from exc
    return Response(status_code=204)


async def fetch_site_models(payload: SiteModelFetchRequest, _: Any = Depends(get_current_admin)) -> list[SiteModelFetchItem]:
    previews = await app_state.store.fetch_models_preview(payload)
    items: list[SiteModelFetchItem] = []
    seen: set[tuple[str, str]] = set()
    for preview in previews:
        channel = ChannelConfig(
            id="preview",
            name=preview["credential_name"] or "preview",
            protocol=payload.protocol,
            base_url=payload.base_url,
            api_key=next(item.api_key for item in payload.credentials if (item.id or "") == preview["credential_id"]),
            headers=payload.headers,
            model_patterns=[],
            keys=[],
            models=[],
            channel_proxy=payload.channel_proxy,
            param_override="",
            match_regex=payload.match_regex,
        )
        for model_name in await _fetch_upstream_models(channel):
            key = (preview["credential_id"], model_name)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                SiteModelFetchItem(
                    credential_id=preview["credential_id"],
                    credential_name=preview["credential_name"],
                    model_name=model_name,
                )
            )
    return items


async def router_snapshot(_: Any = Depends(get_current_admin)) -> dict[str, Any]:
    channels = await app_state.store.list()
    return app_state.router.snapshot(channels).model_dump(mode="json")


async def overview_metrics(_: Any = Depends(get_current_admin)) -> OverviewMetrics:
    metrics = await app_state.domain_store.get_overview_metrics()
    channels = await app_state.store.list()
    return metrics.model_copy(update={"enabled_channels": sum(1 for item in channels if item.status.value == "enabled")})


async def overview_summary(days: int = 7, _: Any = Depends(get_current_admin)) -> OverviewSummary:
    return await app_state.domain_store.get_overview_summary(days=days)


async def overview_daily(days: int = 0, _: Any = Depends(get_current_admin)) -> list[OverviewDailyPoint]:
    return await app_state.domain_store.list_overview_daily(days=days)


async def overview_models(days: int = 7, _: Any = Depends(get_current_admin)) -> OverviewModelAnalytics:
    return await app_state.domain_store.get_model_analytics(days=days)


async def request_logs(_: Any = Depends(get_current_admin)) -> list[RequestLogItem]:
    return await app_state.domain_store.list_request_logs()


async def overview_logs(days: int = 7, limit: int = 50, offset: int = 0, _: Any = Depends(get_current_admin)) -> list[RequestLogItem]:
    return await app_state.domain_store.list_request_logs(limit=limit, days=days, offset=offset)


async def clear_request_logs(_: Any = Depends(get_current_admin)) -> Response:
    await app_state.domain_store.clear_request_logs()
    return Response(status_code=204)


async def request_log_detail(log_id: int, _: Any = Depends(get_current_admin)) -> RequestLogDetail:
    try:
        return await app_state.domain_store.get_request_log(log_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Request log not found: {log_id}") from exc


async def router_preview(payload: RoutePreviewRequest, _: Any = Depends(get_current_admin)) -> dict[str, Any]:
    channels = await app_state.store.list()
    available_channel_ids = {
        channel.id
        for channel in channels
        if app_state.router.is_channel_available(channel.id)
    }
    plan = await _resolve_routing_plan(payload.protocol, payload.model)
    return app_state.router.preview(
        channels,
        payload.protocol,
        payload.model,
        strategy=plan.strategy,
        allowed_channel_ids=available_channel_ids,
        route_targets=plan.route_targets,
        use_model_matching=plan.use_model_matching,
        matched_group_name=plan.matched_group.name if plan.matched_group else None,
    ).model_dump(mode="json")


async def list_model_groups(_: Any = Depends(get_current_admin)) -> list[ModelGroup]:
    return await app_state.domain_store.list_groups()


async def get_model_group(group_id: str, _: Any = Depends(get_current_admin)) -> ModelGroup:
    try:
        return await app_state.domain_store.get_group(group_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Model group not found: {group_id}") from exc


async def list_model_group_stats(_: Any = Depends(get_current_admin)) -> list[ModelGroupStats]:
    return await app_state.domain_store.list_group_stats()


async def list_model_prices(_: Any = Depends(get_current_admin)) -> ModelPriceListResponse:
    await app_state.domain_store.prune_model_prices_to_groups()
    return await app_state.domain_store.list_model_prices()


async def update_model_price(model_key: str, payload: ModelPriceUpdate, _: Any = Depends(get_current_admin)) -> ModelPriceItem:
    try:
        return await app_state.domain_store.upsert_model_price(payload.model_copy(update={"model_key": model_key}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def sync_model_prices(_: Any = Depends(get_current_admin)) -> ModelPriceListResponse:
    await _sync_group_prices(app_state, overwrite_existing=True)
    return await app_state.domain_store.list_model_prices()


async def model_group_candidates(payload: ModelGroupCandidatesRequest, _: Any = Depends(get_current_admin)) -> ModelGroupCandidatesResponse:
    try:
        return await app_state.domain_store.list_group_candidates(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def create_model_group(payload: ModelGroupCreate, _: Any = Depends(get_current_admin)) -> ModelGroup:
    try:
        group = await app_state.domain_store.create_group(payload)
        await _sync_group_prices(app_state)
        return group
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def update_model_group(group_id: str, payload: ModelGroupUpdate, _: Any = Depends(get_current_admin)) -> ModelGroup:
    try:
        group = await app_state.domain_store.update_group(group_id, payload)
        await _sync_group_prices(app_state)
        return group
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Model group not found: {group_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def delete_model_group(group_id: str, _: Any = Depends(get_current_admin)) -> Response:
    try:
        await app_state.domain_store.delete_group(group_id)
        await _sync_group_prices(app_state)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Model group not found: {group_id}") from exc
    return Response(status_code=204)


async def list_settings(_: Any = Depends(get_current_admin)) -> list[SettingItem]:
    return await app_state.domain_store.list_settings()


async def update_settings(payload: SettingsUpdate, _: Any = Depends(get_current_admin)) -> list[SettingItem]:
    normalized_items = []
    for item in payload.items:
        if item.key == SETTING_GATEWAY_API_KEYS:
            normalized_items.append(SettingItem(key=item.key, value=item.value))
            continue
        if item.key == SETTING_GATEWAY_API_KEY_HINT:
            normalized_items.append(SettingItem(key=item.key, value=item.value.strip()))
            continue
        if item.key == SETTING_SITE_NAME:
            normalized_items.append(SettingItem(key=item.key, value=item.value.strip() or "Lens"))
            continue
        if item.key == SETTING_SITE_LOGO_URL:
            normalized_items.append(SettingItem(key=item.key, value=item.value.strip()))
            continue
        normalized_items.append(SettingItem(key=item.key, value=item.value.strip()))
    return await app_state.domain_store.upsert_settings(normalized_items)


async def proxy_openai_chat(request: Request, gateway_key: str = Depends(get_current_gateway_key)):
    body = await request.json()
    return await _proxy_protocol(ProtocolKind.OPENAI_CHAT, body, gateway_key)


async def proxy_openai_responses(request: Request, gateway_key: str = Depends(get_current_gateway_key)):
    body = await request.json()
    return await _proxy_protocol(ProtocolKind.OPENAI_RESPONSES, body, gateway_key)


async def proxy_anthropic_messages(request: Request, gateway_key: str = Depends(get_current_gateway_key)):
    body = await request.json()
    return await _proxy_protocol(ProtocolKind.ANTHROPIC, body, gateway_key)


async def list_gateway_models(_: str = Depends(get_current_gateway_key)) -> dict[str, Any]:
    groups = await app_state.domain_store.list_groups()
    openai_model_names = sorted({
        group.name.strip()
        for group in groups
        if group.name.strip() and group.protocol in {ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_RESPONSES}
    })
    return {
        "object": "list",
        "data": [
            {
                "id": model_name,
                "object": "model",
                "created": 0,
                "owned_by": "lens",
            }
            for model_name in openai_model_names
        ],
    }


async def proxy_gemini_generate_content(model_name: str, request: Request, gateway_key: str = Depends(get_current_gateway_key)):
    body = await request.json()
    body = {**body, "model": model_name, "stream": False}
    return await _proxy_protocol(ProtocolKind.GEMINI, body, gateway_key)


async def proxy_gemini_stream_generate_content(model_name: str, request: Request, gateway_key: str = Depends(get_current_gateway_key)):
    body = await request.json()
    body = {**body, "model": model_name, "stream": True}
    return await _proxy_protocol(ProtocolKind.GEMINI, body, gateway_key)


async def _proxy_protocol(protocol: ProtocolKind, body: dict[str, Any], gateway_key: str) -> Response:
    channels = await app_state.store.list()
    runtime = await app_state.domain_store.get_runtime_settings()
    available_channel_ids = {
        channel.id
        for channel in channels
        if app_state.router.is_channel_available(channel.id)
    }
    started_at = perf_counter()
    requested_model = _requested_model(protocol, body)
    request_content = _dump_json(body)
    plan: RoutingPlan | None = None
    attempts: list[AttemptLog] = []
    try:
        plan = await _resolve_routing_plan(protocol, requested_model)
        selection = app_state.router.select(
            channels,
            protocol,
            plan.requested_model,
            strategy=plan.strategy,
            allowed_channel_ids=available_channel_ids,
            route_targets=plan.route_targets,
            use_model_matching=plan.use_model_matching,
            cursor_key=plan.cursor_key,
        )
    except LookupError as exc:
        await _record_request_log(
            protocol=protocol,
            requested_model=plan.requested_model if plan is not None else requested_model,
            matched_group_name=plan.matched_group.name if plan is not None and plan.matched_group else None,
            channel_id=None,
            channel_name=None,
            gateway_key=gateway_key,
            status_code=503,
            success=False,
            is_stream=bool(body.get("stream")),
            first_token_latency_ms=0,
            latency_ms=_elapsed_ms(started_at),
            request_content=request_content,
            response_content=None,
            attempts=[item.__dict__ for item in attempts],
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

    for target in [selection.primary, *selection.fallbacks]:
        channel = target.channel
        attempt_started_at = perf_counter()
        upstream_body = _prepare_upstream_body(protocol, body, target.model_name)
        try:
            result = await _call_channel(
                channel,
                upstream_body,
                matched_group_name=plan.matched_group.name if plan.matched_group else None,
            )
            attempts.append(
                AttemptLog(
                    channel_id=channel.id,
                    channel_name=channel.name,
                    model_name=target.model_name,
                    status_code=result.status_code,
                    success=True,
                    duration_ms=_elapsed_ms(attempt_started_at),
                )
            )
            if result.is_stream:
                result.response.background = BackgroundTask(
                    _record_stream_request_log,
                    protocol=protocol,
                    requested_model=plan.requested_model,
                    matched_group_name=plan.matched_group.name if plan.matched_group else None,
                    channel=channel,
                    gateway_key=gateway_key,
                    started_at=started_at,
                    upstream_body=upstream_body,
                    result=result,
                    attempts=[item.__dict__ for item in attempts],
                )
                return result.response
            await _record_request_log(
                protocol=protocol,
                requested_model=plan.requested_model,
                matched_group_name=plan.matched_group.name if plan.matched_group else None,
                channel_id=channel.id,
                channel_name=channel.name,
                gateway_key=gateway_key,
                status_code=result.status_code,
                success=True,
                is_stream=result.is_stream,
                first_token_latency_ms=result.first_token_latency_ms,
                latency_ms=_elapsed_ms(started_at),
                resolved_model=result.resolved_model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                input_cost_usd=result.input_cost_usd,
                output_cost_usd=result.output_cost_usd,
                total_cost_usd=result.total_cost_usd,
                request_content=result.request_content or _dump_json(upstream_body),
                response_content=result.response_content,
                attempts=[item.__dict__ for item in attempts],
                error_message=None,
            )
            return result.response
        except HTTPException as exc:
            message = _format_channel_error(channel, exc.detail)
            app_state.router.record_failure(
                channel.id,
                message,
                threshold=int(runtime["circuit_breaker_threshold"]),
                cooldown_seconds=int(runtime["circuit_breaker_cooldown"]),
                max_cooldown_seconds=int(runtime["circuit_breaker_max_cooldown"]),
            )
            errors.append(message)
            attempts.append(
                AttemptLog(
                    channel_id=channel.id,
                    channel_name=channel.name,
                    model_name=target.model_name,
                    status_code=exc.status_code,
                    success=False,
                    duration_ms=_elapsed_ms(attempt_started_at),
                    error_message=message,
                )
            )
            await _record_request_log(
                protocol=protocol,
                requested_model=plan.requested_model,
                matched_group_name=plan.matched_group.name if plan.matched_group else None,
                channel_id=channel.id,
                channel_name=channel.name,
                gateway_key=gateway_key,
                status_code=exc.status_code,
                success=False,
                is_stream=bool(upstream_body.get("stream")),
                first_token_latency_ms=0,
                latency_ms=_elapsed_ms(started_at),
                request_content=_dump_json(upstream_body),
                response_content=None,
                attempts=[item.__dict__ for item in attempts],
                error_message=message,
            )

    error_body = ErrorResponse(
        error={
            "type": "upstream_error",
            "message": "All upstream channels failed",
            "details": errors,
        }
    )
    return JSONResponse(status_code=502, content=error_body.model_dump(mode="json"))


async def _call_channel(channel: ChannelConfig, body: dict[str, Any], matched_group_name: str | None = None) -> UpstreamResult:
    upstream = build_upstream_request(channel, body, settings)
    request_content = _dump_json(upstream.json_body)
    client = app_state.http
    close_client = False
    runtime = await app_state.domain_store.get_runtime_settings()

    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])

    if proxy_url:
        client = httpx.AsyncClient(
            proxy=proxy_url,
            timeout=app_state.http.timeout,
            limits=httpx.Limits(
                max_connections=settings.max_connections,
                max_keepalive_connections=settings.max_keepalive_connections,
            ),
            trust_env=False,
        )
        close_client = True

    try:
        is_stream_request = bool(body.get("stream"))
        stream_started_at = perf_counter()
        if is_stream_request:
            request = client.build_request(
                upstream.method,
                upstream.url,
                headers=upstream.headers,
                json=upstream.json_body,
            )
            response = await client.send(request, stream=True)
        else:
            response = await client.request(
                upstream.method,
                upstream.url,
                headers=upstream.headers,
                json=upstream.json_body,
            )
        response.raise_for_status()
        app_state.router.record_success(channel.id)

        if _is_event_stream_response(response):
            capture = StreamCapture()

            async def iterator():
                try:
                    async for chunk in response.aiter_bytes():
                        if not capture.saw_first_chunk and chunk:
                            capture.saw_first_chunk = True
                            capture.first_token_latency_ms = _elapsed_ms(stream_started_at)
                        _capture_stream_chunk(channel.protocol, chunk, capture)
                        yield chunk
                finally:
                    await response.aclose()

            resolved_model = body.get("model")
            return UpstreamResult(
                response=StreamingResponse(
                    iterator(),
                    status_code=response.status_code,
                    media_type=response.headers.get("content-type"),
                    headers=_passthrough_headers(response.headers),
                ),
                is_stream=True,
                status_code=response.status_code,
                resolved_model=resolved_model,
                first_token_latency_ms=0,
                request_content=request_content,
                response_content=None,
                stream_capture=capture,
            )

        content = response.content if hasattr(response, "content") else await response.aread()

        parsed = _extract_response_usage(channel.protocol, response)
        input_cost_usd, output_cost_usd, total_cost_usd = await app_state.domain_store.estimate_model_cost(
            matched_group_name or parsed["resolved_model"],
            parsed["input_tokens"],
            parsed["output_tokens"],
        )

        return UpstreamResult(
            response=Response(
                content=content,
                status_code=response.status_code,
                media_type=response.headers.get("content-type"),
                headers=_passthrough_headers(response.headers),
            ),
            status_code=response.status_code,
            is_stream=False,
            first_token_latency_ms=0,
            resolved_model=parsed["resolved_model"],
            input_tokens=parsed["input_tokens"],
            output_tokens=parsed["output_tokens"],
            total_tokens=parsed["total_tokens"],
            input_cost_usd=input_cost_usd,
            output_cost_usd=output_cost_usd,
            total_cost_usd=total_cost_usd,
            request_content=request_content,
            response_content=_decode_response_content(response),
        )
    except httpx.HTTPStatusError as exc:
        await exc.response.aread()
        detail = exc.response.text or f"HTTP {exc.response.status_code}"
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=_format_transport_error(exc, upstream.url)) from exc
    finally:
        if close_client:
            await client.aclose()


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


def _is_event_stream_response(response: httpx.Response) -> bool:
    content_type = (response.headers.get("content-type") or "").lower()
    return "text/event-stream" in content_type


def _format_channel_error(channel: ChannelConfig, detail: Any) -> str:
    channel_label = channel.name.strip() or "Unnamed channel"
    detail_text = str(detail).strip() if detail is not None else ""
    if not detail_text:
        detail_text = "Unknown error"
    return f"{channel_label}: {detail_text}"


def _format_transport_error(exc: httpx.HTTPError, fallback_url: str) -> str:
    error_type = exc.__class__.__name__
    request = getattr(exc, "request", None)
    target_url = str(request.url) if request is not None and getattr(request, "url", None) is not None else fallback_url
    target_label = _redact_url_for_error(target_url)
    detail_text = str(exc).strip()
    if detail_text:
        return f"Transport error ({error_type}) while requesting {target_label}: {detail_text}"
    return f"Transport error ({error_type}) while requesting {target_label}"


def _redact_url_for_error(url: str) -> str:
    try:
        parsed = httpx.URL(url)
    except Exception:
        return url
    return str(parsed.copy_with(query=None))


def _requested_model(protocol: ProtocolKind, body: dict[str, Any]) -> str | None:
    if protocol == ProtocolKind.GEMINI:
        return body.get("model")
    return body.get("model")


async def _fetch_upstream_models(channel: ChannelConfig) -> list[str]:
    client = app_state.http
    close_client = False
    runtime = await app_state.domain_store.get_runtime_settings()
    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])

    if proxy_url:
        client = httpx.AsyncClient(
            proxy=proxy_url,
            timeout=app_state.http.timeout,
            limits=httpx.Limits(
                max_connections=settings.max_connections,
                max_keepalive_connections=settings.max_keepalive_connections,
            ),
            trust_env=False,
        )
        close_client = True

    try:
        response = await client.request(**_model_list_request(channel))
        response.raise_for_status()
        return _parse_model_list(channel.protocol, response.json(), channel.match_regex)
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text or f"HTTP {exc.response.status_code}"
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Transport error: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if close_client:
            await client.aclose()


def _model_list_request(channel: ChannelConfig) -> dict[str, Any]:
    base_url = resolve_channel_base_url(channel).rstrip("/")
    api_key = resolve_channel_api_key(channel)
    headers = dict(channel.headers)

    if channel.protocol in {ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_RESPONSES}:
        return {
            "method": "GET",
            "url": f"{base_url}/v1/models",
            "headers": {
                "authorization": f"Bearer {api_key}",
                **headers,
            },
        }

    if channel.protocol == ProtocolKind.ANTHROPIC:
        return {
            "method": "GET",
            "url": f"{base_url}/v1/models",
            "headers": {
                "x-api-key": api_key,
                "anthropic-version": settings.anthropic_version,
                **headers,
            },
        }

    if channel.protocol == ProtocolKind.GEMINI:
        return {
            "method": "GET",
            "url": f"{base_url}/v1beta/models?key={api_key}",
            "headers": headers,
        }

    raise ValueError(f"Unsupported protocol={channel.protocol.value}")


def _parse_model_list(protocol: ProtocolKind, payload: dict[str, Any], match_regex: str) -> list[str]:
    names: list[str] = []
    items = payload.get("data") or payload.get("models") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        if protocol == ProtocolKind.GEMINI:
            value = str(item.get("name") or "")
            if value.startswith("models/"):
                value = value[7:]
        else:
            value = str(item.get("id") or item.get("name") or "")
        value = value.strip()
        if value:
            names.append(value)

    unique_names = list(dict.fromkeys(names))
    if not match_regex.strip():
        return unique_names

    import re

    pattern = re.compile(match_regex)
    return [name for name in unique_names if pattern.search(name)]
async def _resolve_routing_plan(protocol: ProtocolKind, requested_model: str | None) -> RoutingPlan:
    matched_group = await app_state.domain_store.find_group_by_name(protocol.value, requested_model)
    if matched_group is not None:
        channels = await app_state.store.list()
        channel_map = {channel.id: channel for channel in channels}
        route_targets = [
            RouteTarget(channel=channel_map[item.channel_id], model_name=item.model_name)
            for item in matched_group.items
            if item.enabled and item.channel_id in channel_map
        ]
        return RoutingPlan(
            requested_model=requested_model,
            matched_group=matched_group,
            strategy=matched_group.strategy,
            route_targets=route_targets,
            use_model_matching=False,
            cursor_key=f"{protocol.value}:{matched_group.id}",
        )

    if requested_model and protocol in {ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_RESPONSES}:
        raise LookupError(f"No model group matched protocol={protocol.value} model={requested_model}")

    return RoutingPlan(
        requested_model=requested_model,
        matched_group=None,
        strategy=RoutingStrategy.ROUND_ROBIN,
        route_targets=None,
        use_model_matching=True,
    )


def _prepare_upstream_body(protocol: ProtocolKind, body: dict[str, Any], target_model_name: str | None) -> dict[str, Any]:
    payload = deepcopy(body)
    if protocol == ProtocolKind.OPENAI_RESPONSES and "input" in payload:
        payload["input"] = _normalize_openai_responses_input(payload.get("input"))
    if not target_model_name:
        return payload
    if protocol == ProtocolKind.GEMINI:
        payload["model"] = target_model_name
        return payload
    payload["model"] = target_model_name
    return payload


def _normalize_openai_responses_input(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        return [{
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        }]

    if isinstance(value, list):
        normalized_items: list[Any] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                normalized_items.append({
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                })
                continue

            if isinstance(item, dict) and isinstance(item.get("content"), str):
                normalized = dict(item)
                normalized["content"] = [{"type": "input_text", "text": item["content"]}]
                normalized_items.append(normalized)
                continue

            normalized_items.append(item)
        return normalized_items

    return value


def _elapsed_ms(started_at: float) -> int:
    return max(int((perf_counter() - started_at) * 1000), 0)


async def _record_stream_request_log(
    *,
    protocol: ProtocolKind,
    requested_model: str | None,
    matched_group_name: str | None,
    channel: ChannelConfig,
    gateway_key: str,
    started_at: float,
    upstream_body: dict[str, Any],
    result: UpstreamResult,
    attempts: list[dict[str, Any]],
) -> None:
    capture = result.stream_capture
    raw_content = capture.response_content if capture is not None else result.response_content
    parsed = _extract_stream_usage(protocol, raw_content)
    distilled_content = _distill_stream_response_content(protocol, raw_content)
    resolved_model = parsed["resolved_model"] or result.resolved_model
    input_tokens = parsed["input_tokens"]
    output_tokens = parsed["output_tokens"]
    total_tokens = parsed["total_tokens"]
    input_cost_usd, output_cost_usd, total_cost_usd = await app_state.domain_store.estimate_model_cost(
        matched_group_name or resolved_model,
        input_tokens,
        output_tokens,
    )
    await _record_request_log(
        protocol=protocol,
        requested_model=requested_model,
        matched_group_name=matched_group_name,
        channel_id=channel.id,
        channel_name=channel.name,
        gateway_key=gateway_key,
        status_code=result.status_code,
        success=True,
        is_stream=True,
        first_token_latency_ms=capture.first_token_latency_ms if capture is not None else result.first_token_latency_ms,
        latency_ms=_elapsed_ms(started_at),
        resolved_model=resolved_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_cost_usd=input_cost_usd,
        output_cost_usd=output_cost_usd,
        total_cost_usd=total_cost_usd,
        request_content=result.request_content or _dump_json(upstream_body),
        response_content=distilled_content,
        attempts=attempts,
        error_message=None,
    )


async def _record_request_log(
    *,
    protocol: ProtocolKind,
    requested_model: str | None,
    matched_group_name: str | None,
    channel_id: str | None,
    channel_name: str | None,
    gateway_key: str,
    status_code: int,
    success: bool,
    is_stream: bool,
    first_token_latency_ms: int,
    latency_ms: int,
    resolved_model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    input_cost_usd: float = 0.0,
    output_cost_usd: float = 0.0,
    total_cost_usd: float = 0.0,
    request_content: str | None = None,
    response_content: str | None = None,
    attempts: list[dict[str, Any]] | None = None,
    error_message: str | None,
) -> None:
    await app_state.domain_store.create_request_log(
        protocol=protocol.value,
        requested_model=requested_model,
        matched_group_name=matched_group_name,
        channel_id=channel_id,
        channel_name=channel_name,
        gateway_key_id=gateway_key,
        status_code=status_code,
        success=success,
        is_stream=is_stream,
        first_token_latency_ms=first_token_latency_ms,
        latency_ms=latency_ms,
        resolved_model=resolved_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_cost_usd=input_cost_usd,
        output_cost_usd=output_cost_usd,
        total_cost_usd=total_cost_usd,
        request_content=request_content,
        response_content=response_content,
        attempts=attempts,
        error_message=error_message,
    )


def _dump_json(value: Any) -> str | None:
    try:
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return None


def _decode_response_content(response: httpx.Response) -> str | None:
    content = response.content
    if not content:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("utf-8", errors="replace")


def _capture_stream_chunk(protocol: ProtocolKind, chunk: bytes, capture: StreamCapture) -> None:
    text = chunk.decode("utf-8", errors="replace")
    if not text:
        return
    capture.response_content = (capture.response_content or "") + text


def _distill_stream_response_content(protocol: ProtocolKind, raw_content: str | None) -> str | None:
    if not raw_content:
        return None

    if protocol == ProtocolKind.OPENAI_RESPONSES:
        payloads = _parse_sse_payloads(raw_content)
        for payload in reversed(payloads):
            if payload.get("type") != "response.completed":
                continue
            response_payload = payload.get("response")
            if isinstance(response_payload, dict):
                compact_payload = _compact_openai_response_payload(
                    _restore_openai_response_output(response_payload, payloads)
                )
                return _dump_json(compact_payload) or raw_content

    return raw_content


def _compact_openai_response_payload(payload: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in (
        "id",
        "object",
        "model",
        "status",
        "created_at",
        "completed_at",
        "error",
        "incomplete_details",
        "output",
        "usage",
    ):
        value = payload.get(key)
        if value is not None:
            compact[key] = value
    return compact


def _restore_openai_response_output(
    response_payload: dict[str, Any],
    payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    existing_output = response_payload.get("output")
    if isinstance(existing_output, list) and existing_output:
        return response_payload

    rebuilt_output = _rebuild_openai_response_output(payloads)
    if not rebuilt_output:
        return response_payload

    restored_payload = dict(response_payload)
    restored_payload["output"] = rebuilt_output
    return restored_payload


def _rebuild_openai_response_output(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items_by_index: dict[int, dict[str, Any]] = {}
    for payload in payloads:
        payload_type = str(payload.get("type") or "")
        if payload_type in {"response.output_item.added", "response.output_item.done"}:
            output_index = _coerce_openai_output_index(payload.get("output_index"))
            item = payload.get("item")
            if output_index is None or not isinstance(item, dict):
                continue
            items_by_index[output_index] = _merge_openai_output_item(items_by_index.get(output_index), item)
            continue

        if payload_type in {"response.content_part.added", "response.content_part.done"}:
            output_index = _coerce_openai_output_index(payload.get("output_index"))
            content_index = _coerce_openai_output_index(payload.get("content_index"))
            part = payload.get("part")
            if output_index is None or content_index is None or not isinstance(part, dict):
                continue
            item = _ensure_openai_output_message(items_by_index, output_index, payload.get("item_id"))
            _upsert_openai_content_part(item, content_index, part)
            continue

        if payload_type == "response.output_text.delta":
            delta = payload.get("delta")
            if not isinstance(delta, str) or not delta:
                continue
            output_index = _coerce_openai_output_index(payload.get("output_index"), default=0)
            content_index = _coerce_openai_output_index(payload.get("content_index"), default=0)
            item = _ensure_openai_output_message(items_by_index, output_index, payload.get("item_id"))
            _append_openai_output_text(item, content_index, delta)
            continue

        if payload_type == "response.output_text.done":
            text = payload.get("text")
            if not isinstance(text, str):
                continue
            output_index = _coerce_openai_output_index(payload.get("output_index"), default=0)
            content_index = _coerce_openai_output_index(payload.get("content_index"), default=0)
            item = _ensure_openai_output_message(items_by_index, output_index, payload.get("item_id"))
            _set_openai_output_text(item, content_index, text)

    return [items_by_index[index] for index in sorted(items_by_index)]


def _merge_openai_output_item(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(existing) if existing is not None else {}
    for key, value in incoming.items():
        if key == "content" and isinstance(value, list):
            merged[key] = deepcopy(value)
            continue
        merged[key] = value
    if merged.get("type") == "message" and not isinstance(merged.get("content"), list):
        merged["content"] = []
    return merged


def _ensure_openai_output_message(
    items_by_index: dict[int, dict[str, Any]],
    output_index: int,
    item_id: Any,
) -> dict[str, Any]:
    item = items_by_index.get(output_index)
    if item is None:
        item = {"type": "message", "role": "assistant", "content": []}
        items_by_index[output_index] = item
    if item_id and item.get("id") is None:
        item["id"] = str(item_id)
    if item.get("type") == "message" and not isinstance(item.get("content"), list):
        item["content"] = []
    return item


def _upsert_openai_content_part(item: dict[str, Any], content_index: int, part: dict[str, Any]) -> None:
    content = item.setdefault("content", [])
    if not isinstance(content, list):
        content = []
        item["content"] = content
    while len(content) <= content_index:
        content.append(None)
    content[content_index] = deepcopy(part)


def _append_openai_output_text(item: dict[str, Any], content_index: int, delta: str) -> None:
    content = item.setdefault("content", [])
    if not isinstance(content, list):
        content = []
        item["content"] = content
    while len(content) <= content_index:
        content.append(None)
    part = content[content_index]
    if not isinstance(part, dict):
        part = {"type": "output_text", "text": "", "annotations": []}
        content[content_index] = part
    elif part.get("type") != "output_text":
        return
    part["text"] = f"{part.get('text') or ''}{delta}"
    part.setdefault("annotations", [])


def _set_openai_output_text(item: dict[str, Any], content_index: int, text: str) -> None:
    content = item.setdefault("content", [])
    if not isinstance(content, list):
        content = []
        item["content"] = content
    while len(content) <= content_index:
        content.append(None)
    part = content[content_index]
    if not isinstance(part, dict):
        part = {"type": "output_text", "annotations": []}
        content[content_index] = part
    if part.get("type") != "output_text":
        return
    part["text"] = text
    part.setdefault("annotations", [])


def _coerce_openai_output_index(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_stream_usage(protocol: ProtocolKind, raw_content: str | None) -> dict[str, int | str | None]:
    if not raw_content:
        return {"resolved_model": None, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    if protocol == ProtocolKind.GEMINI:
        payloads = _parse_sse_payloads(raw_content)
        if not payloads:
            payloads = _parse_ndjson_payloads(raw_content)
        merged = payloads[-1] if payloads else {}
        if isinstance(merged, dict):
            return _extract_usage_from_payload(protocol, merged)
        return {"resolved_model": None, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    payloads = _parse_sse_payloads(raw_content)
    merged = {"resolved_model": None, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for payload in payloads:
        parsed = _extract_usage_from_payload(protocol, payload)
        if parsed["resolved_model"]:
            merged["resolved_model"] = parsed["resolved_model"]
        if parsed["input_tokens"]:
            merged["input_tokens"] = parsed["input_tokens"]
        if parsed["output_tokens"]:
            merged["output_tokens"] = parsed["output_tokens"]
        if parsed["total_tokens"]:
            merged["total_tokens"] = parsed["total_tokens"]
    if not merged["total_tokens"]:
        merged["total_tokens"] = int(merged["input_tokens"] or 0) + int(merged["output_tokens"] or 0)
    return merged


def _parse_sse_payloads(raw_content: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for block in raw_content.split("\n\n"):
        data_lines = [line[5:].strip() for line in block.splitlines() if line.startswith("data:")]
        if not data_lines:
            continue
        joined = "\n".join(line for line in data_lines if line and line != "[DONE]")
        if not joined:
            continue
        try:
            payload = json.loads(joined)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _parse_ndjson_payloads(raw_content: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for line in raw_content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _extract_usage_from_payload(protocol: ProtocolKind, payload: dict[str, Any]) -> dict[str, int | str | None]:
    if protocol == ProtocolKind.OPENAI_CHAT:
        usage = payload.get("usage") or {}
        return {
            "resolved_model": payload.get("model"),
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
    if protocol == ProtocolKind.OPENAI_RESPONSES:
        if payload.get("type") == "response.completed":
            response_payload = payload.get("response") or {}
            usage = response_payload.get("usage") or {}
            return {
                "resolved_model": response_payload.get("model") or payload.get("model"),
                "input_tokens": int(usage.get("input_tokens") or 0),
                "output_tokens": int(usage.get("output_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
            }
        usage = payload.get("usage") or {}
        return {
            "resolved_model": payload.get("model"),
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
    if protocol == ProtocolKind.ANTHROPIC:
        if payload.get("type") == "message_start":
            message = payload.get("message") or {}
            usage = message.get("usage") or {}
            input_tokens = int(usage.get("input_tokens") or 0)
            output_tokens = int(usage.get("output_tokens") or 0)
            return {
                "resolved_model": message.get("model"),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            }
        if payload.get("type") == "message_delta":
            delta = payload.get("usage") or {}
            output_tokens = int(delta.get("output_tokens") or 0)
            return {
                "resolved_model": None,
                "input_tokens": 0,
                "output_tokens": output_tokens,
                "total_tokens": output_tokens,
            }
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


async def _sync_group_prices(state: AppState, overwrite_existing: bool = False) -> None:
    group_names = await state.domain_store.list_group_names()
    if not group_names:
        await state.domain_store.replace_model_prices([])
        return

    try:
        response = await state.http.get('https://models.dev/api.json')
        response.raise_for_status()
        price_index = build_models_dev_price_index(response.json())
        payloads = build_group_price_payloads(group_names, price_index)
        await state.domain_store.sync_model_prices(payloads, overwrite_existing=overwrite_existing, allowed_keys=group_names)
        await state.domain_store.set_model_price_sync_time(datetime.now(UTC).isoformat())
    except Exception:
        return


app = create_app(service_module=__import__(__name__, fromlist=["*"]))
