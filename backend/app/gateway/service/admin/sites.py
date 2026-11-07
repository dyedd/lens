from __future__ import annotations

from typing import Any, Literal

from fastapi import Depends, HTTPException, Query, Request, Response

from ....core.errors import ModelDiscoveryError, ResourceNotFoundError
from ....core.model_protocols import ENDPOINT_KIND_PROTOCOLS, resolve_onboard_protocol
from ....models.channels import (
    ChannelConfig,
    ChannelModelSyncRequest,
    ChannelModelSyncResponse,
)
from ....models.endpoint_probe import EndpointProbeRequest, EndpointProbeResult
from ....models.health import HealthSummary
from ....models.model_groups import ModelGroupItemState
from ....models.protocols import ProtocolKind
from ....models.site_import import SiteBatchImportRequest, SiteBatchImportResult
from ....models.site_model_test import (
    ModelContextDetectionRequest,
    SiteModelFetchItem,
    SiteModelFetchRequest,
    SiteModelProtocolDetectionRequest,
    SiteModelProtocolDetectionResult,
    SiteModelTestRequest,
    SiteModelTestResult,
)
from ....models.sites import (
    SiteConfig,
    SiteCreate,
    SiteCredential,
    SiteEnabledUpdate,
    SiteUpdate,
)
from ...router.targets import RouteTarget, target_key
from ..app_state import app_state
from ..auth import get_current_admin
from ..tasks.litellm_sync_tasks import (
    ModelPriceSyncError,
    fetch_context_windows,
    find_context_window,
)
from ..tasks.model_discovery import (
    fetch_upstream_model_list,
    model_list_protocols,
)
from ..tasks.model_group_reconcile import run_model_group_reconcile
from ..tasks.site_model_probe import run_site_model_probe
from ..upstream_support import format_channel_error


async def list_sites(
    tag: str | None = None, _: Any = Depends(get_current_admin)
) -> list[SiteConfig]:
    """List configured upstream sites."""
    return await app_state.channel_store.list_sites(tag=tag)


async def list_model_health(
    hours: int = Query(default=6),
    mode: Literal["model", "channel"] = "model",
    query: str = Query(default="", max_length=120),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: Any = Depends(get_current_admin),
) -> HealthSummary:
    """List request-log health by execution model group or site."""
    if hours not in (1, 6, 24):
        raise HTTPException(status_code=422, detail="hours must be 1, 6, or 24")
    summary = await app_state.request_log_store.queries.list_model_health(
        hours=hours,
        mode=mode,
        query=query,
        limit=limit,
        offset=offset,
    )
    channels = await app_state.channel_store.list_channels()
    targets_by_id = await _health_targets(mode, channels)
    targets = [
        target for item in summary.items for target in targets_by_id.get(item.id, [])
    ]
    cooldowns = app_state.router.cooldown_remaining_by_target(channels, targets)
    for item in summary.items:
        item.cooldown_remaining_seconds = max(
            (
                cooldowns[target_key(target)]
                for target in targets_by_id.get(item.id, [])
            ),
            default=0,
        )
    return summary


async def reset_health_cooldown(
    item_id: str,
    mode: Literal["model", "channel"] = "model",
    _: Any = Depends(get_current_admin),
) -> Response:
    channels = await app_state.channel_store.list_channels()
    targets_by_id = await _health_targets(mode, channels)
    if item_id not in targets_by_id:
        raise ResourceNotFoundError(item_id)
    app_state.router.reset_cooldowns(targets_by_id[item_id])
    return Response(status_code=204)


async def _health_targets(
    mode: Literal["model", "channel"], channels: list[ChannelConfig]
) -> dict[str, list[RouteTarget]]:
    if mode == "model":
        channel_map = {channel.id: channel for channel in channels}
        groups = await app_state.group_repo.list_groups(channels=channels)
        return {
            group.id: [
                RouteTarget(
                    channel=channel_map[item.channel_id],
                    model_name=item.model_name,
                    credential_id=item.credential_id,
                )
                for item in group.items
                if item.state == ModelGroupItemState.READY
            ]
            for group in groups
            if not group.route_group_id
        }

    targets_by_id: dict[str, list[RouteTarget]] = {}
    for channel in channels:
        targets = targets_by_id.setdefault(channel.site_id, [])
        credential_ids = {key.id for key in channel.keys}
        targets.extend(
            RouteTarget(
                channel=channel,
                model_name=model.model_name,
                credential_id=model.credential_id,
            )
            for model in channel.models
            if model.enabled
            and (not channel.keys or model.credential_id in credential_ids)
        )
        if not channel.models:
            targets.extend(
                RouteTarget(channel=channel, credential_id=credential_id)
                for credential_id in credential_ids or {""}
            )
    return targets_by_id


async def create_site(
    payload: SiteCreate, _: Any = Depends(get_current_admin)
) -> SiteConfig:
    """Create an upstream site."""
    site = await app_state.channel_store.create_site(payload)
    await run_model_group_reconcile(app_state)
    return site


async def import_sites(
    payload: SiteBatchImportRequest, _: Any = Depends(get_current_admin)
) -> SiteBatchImportResult:
    """Import upstream sites from a validated batch payload."""
    result = await app_state.channel_store.import_sites(payload)
    await run_model_group_reconcile(app_state)
    return result


async def update_site(
    site_id: str, payload: SiteUpdate, _: Any = Depends(get_current_admin)
) -> SiteConfig:
    """Update an upstream site."""
    site = await app_state.channel_store.update_site(site_id, payload)
    await run_model_group_reconcile(app_state)
    return site


async def update_site_enabled(
    site_id: str,
    payload: SiteEnabledUpdate,
    _: Any = Depends(get_current_admin),
) -> SiteConfig:
    """Update an upstream site's master enabled state."""
    site = await app_state.channel_store.update_site_enabled(site_id, payload)
    await run_model_group_reconcile(app_state)
    return site


async def delete_site(site_id: str, _: Any = Depends(get_current_admin)) -> Response:
    """Delete an upstream site."""
    await app_state.channel_store.delete_site(site_id)
    return Response(status_code=204)


async def fetch_site_models(
    payload: SiteModelFetchRequest, _: Any = Depends(get_current_admin)
) -> list[SiteModelFetchItem]:
    """Discover models available through the supplied site credentials."""
    previews = app_state.channel_store.fetch_models_preview(payload)
    listing_protocols = (payload.protocol,) if payload.protocol is not None else None
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
            protocol=payload.protocol or ProtocolKind.OPENAI_CHAT,
            base_url=payload.base_url,
            endpoint_kind=payload.endpoint_kind,
            model_list_url=payload.base_url
            if payload.endpoint_kind == "models"
            else None,
            api_key=credential.api_key,
            headers=payload.headers,
            model_patterns=[],
            keys=[
                {
                    "id": preview["credential_id"],
                    "key": credential.api_key,
                    "remark": preview["credential_name"],
                }
            ],
            models=[],
            proxy_mode=payload.proxy_mode,
            channel_proxy=payload.channel_proxy,
            param_override=[],
        )
        try:
            model_list = await fetch_upstream_model_list(channel, listing_protocols)
        except ModelDiscoveryError as exc:
            errors.append(format_channel_error(exc.public_message))
            continue

        for upstream_model in model_list.models:
            key = (preview["credential_id"], upstream_model.name)
            if key in seen:
                continue
            seen.add(key)
            items.extend(
                SiteModelFetchItem(
                    credential_id=preview["credential_id"],
                    credential_name=preview["credential_name"],
                    model_name=upstream_model.name,
                    protocol=protocol,
                )
                for protocol in model_list_protocols(
                    upstream_model, model_list.protocol, payload.endpoint_kind
                )
            )
    if not items and errors:
        raise HTTPException(
            status_code=502,
            detail="Model discovery failed: " + "; ".join(errors),
        )
    return items


async def detect_model_contexts(
    payload: ModelContextDetectionRequest,
    _: Any = Depends(get_current_admin),
) -> dict[str, int | None]:
    try:
        windows = await fetch_context_windows(app_state)
    except ModelPriceSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {name: find_context_window(windows, name) for name in payload.model_names}


async def detect_site_model_protocols(
    payload: SiteModelProtocolDetectionRequest,
    _: Any = Depends(get_current_admin),
) -> list[SiteModelProtocolDetectionResult]:
    """为模型生成默认协议预选值。"""
    pinned = ENDPOINT_KIND_PROTOCOLS.get(payload.endpoint_kind)
    return [
        SiteModelProtocolDetectionResult(
            model_name=name,
            protocols=[resolve_onboard_protocol(name, pinned=pinned)],
        )
        for name in payload.model_names
    ]


async def test_site_model(
    payload: SiteModelTestRequest,
    request: Request,
    _: Any = Depends(get_current_admin),
) -> SiteModelTestResult:
    """Probe one site model with the supplied request settings."""
    return await run_site_model_probe(payload, request)


async def probe_endpoint_latency(
    payload: EndpointProbeRequest, _: Any = Depends(get_current_admin)
) -> EndpointProbeResult:
    """Time one upstream address from the gateway host."""
    from ..tasks.endpoint_probe import probe_endpoint

    return await probe_endpoint(payload)


async def sync_channel_models(
    payload: ChannelModelSyncRequest, _: Any = Depends(get_current_admin)
) -> ChannelModelSyncResponse:
    """Sync filtered upstream models for enabled sites."""
    from ..tasks.model_sync import sync_channel_models as run_channel_model_sync

    return await run_channel_model_sync(
        app_state,
        site_ids=payload.site_ids,
        credential_ids=payload.credential_ids,
    )


async def list_model_sync_runs(
    limit: int = Query(default=20, ge=1, le=100),
    _: Any = Depends(get_current_admin),
) -> list[ChannelModelSyncResponse]:
    """List recorded model sync runs, newest first."""
    return await app_state.model_sync_run_repo.list_runs(limit=limit)


async def sync_site_credential_rate(
    site_id: str,
    credential_id: str,
    _: Any = Depends(get_current_admin),
) -> SiteCredential:
    """Synchronize one configured upstream credential rate."""
    from ..tasks.credential_rate_tasks import (
        CredentialRateConflictError,
        CredentialRateNotConfiguredError,
        CredentialRateSyncError,
    )
    from ..tasks.credential_rate_tasks import (
        sync_site_credential_rate as run_credential_rate_sync,
    )

    try:
        return await run_credential_rate_sync(app_state, site_id, credential_id)
    except CredentialRateNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CredentialRateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CredentialRateSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
