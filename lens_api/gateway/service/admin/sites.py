from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Response

from ....models import (
    ChannelConfig,
    ChannelModelSyncRequest,
    ChannelModelSyncResponse,
    ProtocolKind,
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
)
from ..auth import get_current_admin
from ..site_model_probe import (
    _apply_site_model_probe_param_override,
    _call_site_model_probe_channel,
    _site_model_probe_body,
    _site_model_probe_channel,
)
from ..app_state import app_state
from ..model_discovery import _fetch_upstream_models
from ..upstream_support import _format_channel_error


async def list_sites(_: Any = Depends(get_current_admin)) -> list[SiteConfig]:
    """List configured upstream sites."""
    return await app_state.channel_store.list_sites()


async def list_site_runtime_summaries(
    _: Any = Depends(get_current_admin),
) -> list[SiteRuntimeSummary]:
    """List runtime health summaries for upstream sites."""
    return await app_state.request_log_store.list_site_runtime_summaries()


async def create_site(
    payload: SiteCreate, _: Any = Depends(get_current_admin)
) -> SiteConfig:
    """Create an upstream site."""
    return await app_state.channel_store.create_site(payload)


async def import_sites(
    payload: SiteBatchImportRequest, _: Any = Depends(get_current_admin)
) -> SiteBatchImportResult:
    """Import upstream sites from a validated batch payload."""
    return await app_state.channel_store.import_sites(payload)


async def update_site(
    site_id: str, payload: SiteUpdate, _: Any = Depends(get_current_admin)
) -> SiteConfig:
    """Update an upstream site."""
    return await app_state.channel_store.update_site(site_id, payload)


async def delete_site(site_id: str, _: Any = Depends(get_current_admin)) -> Response:
    """Delete an upstream site."""
    await app_state.channel_store.delete_site(site_id)
    return Response(status_code=204)


async def fetch_site_models(
    payload: SiteModelFetchRequest, _: Any = Depends(get_current_admin)
) -> list[SiteModelFetchItem]:
    """Discover models available through the supplied site credentials."""
    previews = await app_state.channel_store.fetch_models_preview(payload)
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
            proxy_mode=payload.proxy_mode,
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
    """Probe one site model with the supplied request settings."""
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


async def sync_channel_models(
    payload: ChannelModelSyncRequest, _: Any = Depends(get_current_admin)
) -> ChannelModelSyncResponse:
    """Synchronize stored channel models with their upstream sites."""
    from ..model_sync import sync_channel_models as run_channel_model_sync

    return await run_channel_model_sync(app_state, dry_run=payload.dry_run)
