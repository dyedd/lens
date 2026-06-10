from __future__ import annotations

from .runtime_context import (
    Any,
    ChannelConfig,
    Depends,
    HTTPException,
    OverviewDailyPoint,
    OverviewModelAnalytics,
    OverviewSummary,
    ProtocolKind,
    Query,
    RequestLogDetail,
    RequestLogItem,
    RequestLogPage,
    RequestLogSortMode,
    RequestLogStatusFilter,
    Response,
    RoutePreviewRequest,
    RoutingStrategy,
    SiteBatchImportRequest,
    SiteBatchImportResult,
    SiteConfig,
    SiteCreate,
    SiteModelFetchItem,
    SiteModelFetchRequest,
    SiteModelTestRequest,
    SiteModelTestResult,
    SiteRuntimeSummary,
    SiteUpdate,
    app_state,
)
from .errors import _apply_router_runtime_settings
from .upstream_http import (
    _fetch_upstream_models,
    _format_channel_error,
)
from .routing_plan import _resolve_routing_plan
from .site_model_probe import (
    _apply_site_model_probe_param_override,
    _call_site_model_probe_channel,
    _site_model_probe_body,
    _site_model_probe_channel,
)
from .auth import get_current_admin


async def list_sites(_: Any = Depends(get_current_admin)) -> list[SiteConfig]:
    return await app_state.store.list_sites()


async def site_runtime_summaries(
    _: Any = Depends(get_current_admin),
) -> list[SiteRuntimeSummary]:
    return await app_state.domain_store.list_site_runtime_summaries()


async def create_site(
    payload: SiteCreate, _: Any = Depends(get_current_admin)
) -> SiteConfig:
    return await app_state.store.create_site(payload)


async def import_sites(
    payload: SiteBatchImportRequest, _: Any = Depends(get_current_admin)
) -> SiteBatchImportResult:
    return await app_state.store.import_sites(payload)


async def update_site(
    site_id: str, payload: SiteUpdate, _: Any = Depends(get_current_admin)
) -> SiteConfig:
    return await app_state.store.update_site(site_id, payload)


async def delete_site(site_id: str, _: Any = Depends(get_current_admin)) -> Response:
    await app_state.store.delete_site(site_id)
    return Response(status_code=204)


async def fetch_site_models(
    payload: SiteModelFetchRequest, _: Any = Depends(get_current_admin)
) -> list[SiteModelFetchItem]:
    previews = await app_state.store.fetch_models_preview(payload)
    items: list[SiteModelFetchItem] = []
    seen: set[tuple[str, str]] = set()
    errors: list[str] = []

    for preview in previews:
        credential = next(
            (
                item
                for item in payload.credentials
                if (item.id or "") == preview["credential_id"]
            ),
            None,
        )
        if credential is None:
            continue

        channel = ChannelConfig(
            id="preview",
            name=preview["credential_name"] or "preview",
            protocol=ProtocolKind.OPENAI_CHAT,
            base_url=payload.base_url,
            api_key=credential.api_key,
            headers=payload.headers,
            model_patterns=[],
            keys=[
                {
                    "id": preview["credential_id"],
                    "key": credential.api_key,
                    "remark": preview["credential_name"],
                    "enabled": True,
                }
            ],
            models=[],
            channel_proxy=payload.channel_proxy,
            param_override="",
            match_regex=payload.match_regex,
        )
        try:
            model_names = await _fetch_upstream_models(channel)
        except HTTPException as exc:
            errors.append(_format_channel_error(exc.detail))
            continue

        for model_name in model_names:
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
    if not items and errors:
        raise HTTPException(
            status_code=502,
            detail="Model discovery failed: " + "; ".join(errors),
        )
    return items


async def test_site_model(
    payload: SiteModelTestRequest, _: Any = Depends(get_current_admin)
) -> SiteModelTestResult:
    channel = _site_model_probe_channel(payload)
    body = _site_model_probe_body(payload)
    prepared_body = _apply_site_model_probe_param_override(channel, body, payload)
    if isinstance(prepared_body, SiteModelTestResult):
        return prepared_body
    return await _call_site_model_probe_channel(
        channel=channel,
        body=prepared_body,
        model_name=payload.model_name,
        credential_id=payload.credential.id,
    )


async def router_snapshot(_: Any = Depends(get_current_admin)) -> dict[str, Any]:
    channels = await app_state.store.list()
    return app_state.router.snapshot(channels).model_dump(mode="json")


async def overview_summary(
    days: int = 7,
    _: Any = Depends(get_current_admin),
) -> OverviewSummary:
    return await app_state.domain_store.get_overview_summary(
        days=days,
    )


async def overview_daily(
    days: int = 0,
    _: Any = Depends(get_current_admin),
) -> list[OverviewDailyPoint]:
    return await app_state.domain_store.list_overview_daily(
        days=days,
    )


async def overview_models(
    days: int = 7,
    metric: str = Query(default="cost", pattern="^(cost|requests|tokens)$"),
    gateway_key_id: str | None = None,
    _: Any = Depends(get_current_admin),
) -> OverviewModelAnalytics:
    return await app_state.domain_store.get_model_analytics(
        days=days,
        metric=metric,
        gateway_key_id=gateway_key_id,
    )


async def request_logs(
    limit: int = 100,
    offset: int = 0,
    gateway_key_id: str | None = None,
    _: Any = Depends(get_current_admin),
) -> list[RequestLogItem]:
    return await app_state.domain_store.list_request_logs(
        limit=limit,
        offset=offset,
        gateway_key_id=gateway_key_id,
    )


async def request_log_page(
    limit: int = 100,
    offset: int = 0,
    gateway_key_id: str | None = None,
    model_prefix: str | None = None,
    status_filter: RequestLogStatusFilter | None = Query(default=None, alias="status"),
    protocol: ProtocolKind | None = None,
    channel: str | None = None,
    keyword: str | None = None,
    sort: RequestLogSortMode = RequestLogSortMode.LATEST,
    _: Any = Depends(get_current_admin),
) -> RequestLogPage:
    return await app_state.domain_store.list_request_log_page(
        limit=limit,
        offset=offset,
        gateway_key_id=gateway_key_id,
        model_prefix=model_prefix,
        status_filter=status_filter,
        protocol=protocol,
        channel=channel,
        keyword=keyword,
        sort=sort,
    )


async def clear_request_logs(_: Any = Depends(get_current_admin)) -> Response:
    await app_state.domain_store.clear_request_logs()
    return Response(status_code=204)


async def request_log_detail(
    log_id: int, _: Any = Depends(get_current_admin)
) -> RequestLogDetail:
    return await app_state.domain_store.get_request_log(log_id)


async def router_preview(
    payload: RoutePreviewRequest, _: Any = Depends(get_current_admin)
) -> dict[str, Any]:
    channels = await app_state.store.list()
    runtime = await app_state.domain_store.get_runtime_settings()
    _apply_router_runtime_settings(runtime)
    if not payload.model:
        return app_state.router.preview(
            channels,
            payload.protocol,
            None,
            strategy=RoutingStrategy.ROUND_ROBIN,
            route_targets=None,
            use_model_matching=True,
        ).model_dump(mode="json")
    plan = await _resolve_routing_plan(payload.protocol, payload.model, channels)
    return app_state.router.preview(
        channels,
        payload.protocol,
        plan.resolved_group_name or payload.model,
        strategy=plan.strategy,
        route_targets=plan.route_targets,
        use_model_matching=plan.use_model_matching,
        requested_group_name=plan.requested_group_name,
        resolved_group_name=plan.resolved_group_name,
        cursor_key=plan.cursor_key,
    ).model_dump(mode="json")
