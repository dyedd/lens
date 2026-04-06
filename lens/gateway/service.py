from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from time import perf_counter
from typing import Any
from copy import deepcopy

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from ..core.auth import create_access_token, decode_access_token
from ..core.config import settings
from ..core.db import create_engine, create_session_factory
from ..core.model_prices import build_group_price_payloads, build_models_dev_price_index
from ..models import AdminLoginRequest, AdminProfile, AuthTokenResponse, ErrorResponse, ModelGroup, ModelGroupCandidatesRequest, ModelGroupCandidatesResponse, ModelGroupCreate, ModelGroupStats, ModelGroupUpdate, ModelPriceItem, ModelPriceListResponse, ModelPriceUpdate, OverviewDailyPoint, OverviewMetrics, OverviewModelAnalytics, OverviewSummary, ProtocolKind, ChannelConfig, RequestLogItem, RoutePreviewRequest, RoutingStrategy, SettingItem, SettingsUpdate, SiteConfig, SiteCreate, SiteModelFetchItem, SiteModelFetchRequest, SiteUpdate
from ..persistence.admin_store import AdminStore
from ..persistence.domain_store import DomainStore
from ..persistence.channel_store import ChannelStore
from .router import RoundRobinRouter, RouteTarget
from .upstreams import build_upstream_request, resolve_channel_api_key, resolve_channel_base_url, resolve_channel_proxy_url


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
    await state.admin_store.ensure_default_admin(settings.admin_default_username, settings.admin_default_password)
    await _bootstrap_imported_stats(state)
    await _sync_group_prices(state)


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


@app.get("/api/sites")
async def list_sites(_: Any = Depends(get_current_admin)) -> list[SiteConfig]:
    return await app_state.store.list_sites()


@app.post("/api/sites", status_code=201)
async def create_site(payload: SiteCreate, _: Any = Depends(get_current_admin)) -> SiteConfig:
    return await app_state.store.create_site(payload)


@app.put("/api/sites/{site_id}")
async def update_site(site_id: str, payload: SiteUpdate, _: Any = Depends(get_current_admin)) -> SiteConfig:
    try:
        return await app_state.store.update_site(site_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Site not found: {site_id}") from exc


@app.delete("/api/sites/{site_id}", status_code=204)
async def delete_site(site_id: str, _: Any = Depends(get_current_admin)) -> Response:
    try:
        await app_state.store.delete_site(site_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Site not found: {site_id}") from exc
    return Response(status_code=204)


@app.post("/api/sites/fetch-models", response_model=list[SiteModelFetchItem])
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


@app.get("/api/router")
async def router_snapshot(_: Any = Depends(get_current_admin)) -> dict[str, Any]:
    channels = await app_state.store.list()
    return app_state.router.snapshot(channels).model_dump(mode="json")


@app.get("/api/overview", response_model=OverviewMetrics)
async def overview_metrics(_: Any = Depends(get_current_admin)) -> OverviewMetrics:
    metrics = await app_state.domain_store.get_overview_metrics()
    channels = await app_state.store.list()
    return metrics.model_copy(update={"enabled_channels": sum(1 for item in channels if item.status.value == "enabled")})


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
    channels = await app_state.store.list()
    plan = await _resolve_routing_plan(payload.protocol, payload.model)
    return app_state.router.preview(
        channels,
        payload.protocol,
        payload.model,
        strategy=plan.strategy,
        route_targets=plan.route_targets,
        use_model_matching=plan.use_model_matching,
        matched_group_name=plan.matched_group.name if plan.matched_group else None,
    ).model_dump(mode="json")


@app.get("/api/model-groups", response_model=list[ModelGroup])
async def list_model_groups(_: Any = Depends(get_current_admin)) -> list[ModelGroup]:
    return await app_state.domain_store.list_groups()


@app.get("/api/model-groups/{group_id}", response_model=ModelGroup)
async def get_model_group(group_id: str, _: Any = Depends(get_current_admin)) -> ModelGroup:
    try:
        return await app_state.domain_store.get_group(group_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Model group not found: {group_id}") from exc


@app.get("/api/model-groups/stats", response_model=list[ModelGroupStats])
async def list_model_group_stats(_: Any = Depends(get_current_admin)) -> list[ModelGroupStats]:
    return await app_state.domain_store.list_group_stats()


@app.get("/api/model-prices", response_model=ModelPriceListResponse)
async def list_model_prices(_: Any = Depends(get_current_admin)) -> ModelPriceListResponse:
    await app_state.domain_store.prune_model_prices_to_groups()
    return await app_state.domain_store.list_model_prices()


@app.put("/api/model-prices/{model_key}", response_model=ModelPriceItem)
async def update_model_price(model_key: str, payload: ModelPriceUpdate, _: Any = Depends(get_current_admin)) -> ModelPriceItem:
    try:
        return await app_state.domain_store.upsert_model_price(payload.model_copy(update={"model_key": model_key}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/model-prices/sync", response_model=ModelPriceListResponse)
async def sync_model_prices(_: Any = Depends(get_current_admin)) -> ModelPriceListResponse:
    await _sync_group_prices(app_state, overwrite_existing=True)
    return await app_state.domain_store.list_model_prices()


@app.post("/api/model-groups/candidates", response_model=ModelGroupCandidatesResponse)
async def model_group_candidates(payload: ModelGroupCandidatesRequest, _: Any = Depends(get_current_admin)) -> ModelGroupCandidatesResponse:
    try:
        return await app_state.domain_store.list_group_candidates(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/model-groups", response_model=ModelGroup, status_code=201)
async def create_model_group(payload: ModelGroupCreate, _: Any = Depends(get_current_admin)) -> ModelGroup:
    try:
        group = await app_state.domain_store.create_group(payload)
        await _sync_group_prices(app_state)
        return group
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/model-groups/{group_id}", response_model=ModelGroup)
async def update_model_group(group_id: str, payload: ModelGroupUpdate, _: Any = Depends(get_current_admin)) -> ModelGroup:
    try:
        group = await app_state.domain_store.update_group(group_id, payload)
        await _sync_group_prices(app_state)
        return group
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Model group not found: {group_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/model-groups/{group_id}", status_code=204)
async def delete_model_group(group_id: str, _: Any = Depends(get_current_admin)) -> Response:
    try:
        await app_state.domain_store.delete_group(group_id)
        await _sync_group_prices(app_state)
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
    channels = await app_state.store.list()
    plan = await _resolve_routing_plan(protocol, _requested_model(protocol, body))
    started_at = perf_counter()
    try:
        selection = app_state.router.select(
            channels,
            protocol,
            plan.requested_model,
            strategy=plan.strategy,
            route_targets=plan.route_targets,
            use_model_matching=plan.use_model_matching,
            cursor_key=plan.cursor_key,
        )
    except LookupError as exc:
        await _record_request_log(
            protocol=protocol,
            requested_model=plan.requested_model,
            matched_group_name=plan.matched_group.name if plan.matched_group else None,
            channel_id=None,
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

    for target in [selection.primary, *selection.fallbacks]:
        channel = target.channel
        try:
            result = await _call_channel(
                channel,
                _prepare_upstream_body(protocol, body, target.model_name),
                matched_group_name=plan.matched_group.name if plan.matched_group else None,
            )
            await _record_request_log(
                protocol=protocol,
                requested_model=plan.requested_model,
                matched_group_name=plan.matched_group.name if plan.matched_group else None,
                channel_id=channel.id,
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
            message = f"{channel.id}: {exc.detail}"
            app_state.router.record_failure(channel.id, message)
            errors.append(message)
            await _record_request_log(
                protocol=protocol,
                requested_model=plan.requested_model,
                matched_group_name=plan.matched_group.name if plan.matched_group else None,
                channel_id=channel.id,
                gateway_key=gateway_key,
                status_code=exc.status_code,
                success=False,
                latency_ms=_elapsed_ms(started_at),
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
    stream = bool(body.get("stream"))
    client = app_state.http
    close_client = False

    if upstream.proxy_url:
        client = httpx.AsyncClient(
            proxy=upstream.proxy_url,
            timeout=app_state.http.timeout,
            limits=httpx.Limits(
                max_connections=settings.max_connections,
                max_keepalive_connections=settings.max_keepalive_connections,
            ),
            trust_env=False,
        )
        close_client = True

    try:
        if stream:
            request = client.build_request(
                upstream.method,
                upstream.url,
                headers=upstream.headers,
                json=upstream.json_body,
            )
            response = await client.send(request, stream=True)
            response.raise_for_status()
            app_state.router.record_success(channel.id)

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
                resolved_model=body.get("model"),
            )

        response = await client.request(
            upstream.method,
            upstream.url,
            headers=upstream.headers,
            json=upstream.json_body,
        )
        response.raise_for_status()
        app_state.router.record_success(channel.id)

        parsed = _extract_response_usage(channel.protocol, response)
        input_cost_usd, output_cost_usd, total_cost_usd = await app_state.domain_store.estimate_model_cost(
            matched_group_name or parsed["resolved_model"],
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


def _requested_model(protocol: ProtocolKind, body: dict[str, Any]) -> str | None:
    if protocol == ProtocolKind.GEMINI:
        return body.get("model")
    return body.get("model")


async def _fetch_upstream_models(channel: ChannelConfig) -> list[str]:
    client = app_state.http
    close_client = False
    proxy_url = resolve_channel_proxy_url(channel)

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

    return RoutingPlan(
        requested_model=requested_model,
        matched_group=None,
        strategy=RoutingStrategy.ROUND_ROBIN,
        route_targets=None,
        use_model_matching=True,
    )


def _prepare_upstream_body(protocol: ProtocolKind, body: dict[str, Any], target_model_name: str | None) -> dict[str, Any]:
    payload = deepcopy(body)
    if not target_model_name:
        return payload
    if protocol == ProtocolKind.GEMINI:
        payload["model"] = target_model_name
        return payload
    payload["model"] = target_model_name
    return payload


def _elapsed_ms(started_at: float) -> int:
    return max(int((perf_counter() - started_at) * 1000), 0)


async def _record_request_log(
    *,
    protocol: ProtocolKind,
    requested_model: str | None,
    matched_group_name: str | None,
    channel_id: str | None,
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
        channel_id=channel_id,
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
                    "cache_read_price_per_million": item.get("cache_read_input") or item.get("cache_read"),
                    "cache_write_price_per_million": item.get("cache_creation_input") or item.get("cache_write"),
                }
                for item in payload.get("llm_infos", [])
                if item.get("name")
            ],
        )
    except Exception:
        return


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


