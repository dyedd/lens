from __future__ import annotations

from typing import Any, Literal

from fastapi import Depends, HTTPException, Query, Request, Response

from ....models.channels import (
    ChannelConfig,
    ChannelModelSyncRequest,
    ChannelModelSyncResponse,
)
from ....models.health import HealthSummary
from ....models.protocols import ProtocolKind
from ....models.site_import import SiteBatchImportRequest, SiteBatchImportResult
from ....models.site_model_test import (
    SiteModelFetchItem,
    SiteModelFetchRequest,
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
from ..app_state import app_state
from ..auth import get_current_admin
from ..tasks.model_discovery import fetch_upstream_models, filter_model_names
from ..tasks.model_group_placement import run_model_group_placement
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
    return await app_state.request_log_store.list_model_health(
        hours=hours,
        mode=mode,
        query=query,
        limit=limit,
        offset=offset,
    )


async def create_site(
    payload: SiteCreate, _: Any = Depends(get_current_admin)
) -> SiteConfig:
    """Create an upstream site."""
    site = await app_state.channel_store.create_site(payload)
    await run_model_group_placement(app_state)
    return site


async def import_sites(
    payload: SiteBatchImportRequest, _: Any = Depends(get_current_admin)
) -> SiteBatchImportResult:
    """Import upstream sites from a validated batch payload."""
    result = await app_state.channel_store.import_sites(payload)
    await run_model_group_placement(app_state)
    return result


async def update_site(
    site_id: str, payload: SiteUpdate, _: Any = Depends(get_current_admin)
) -> SiteConfig:
    """Update an upstream site."""
    site = await app_state.channel_store.update_site(site_id, payload)
    await run_model_group_placement(app_state)
    return site


async def update_site_enabled(
    site_id: str,
    payload: SiteEnabledUpdate,
    _: Any = Depends(get_current_admin),
) -> SiteConfig:
    """Update an upstream site's master enabled state."""
    site = await app_state.channel_store.update_site_enabled(site_id, payload)
    await run_model_group_placement(app_state)
    return site


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
                }
            ],
            models=[],
            proxy_mode=payload.proxy_mode,
            channel_proxy=payload.channel_proxy,
            param_override=[],
        )
        try:
            model_names = filter_model_names(
                await fetch_upstream_models(channel), payload.match_regex
            )
        except HTTPException as exc:
            errors.append(format_channel_error(exc.detail))
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
    payload: SiteModelTestRequest,
    request: Request,
    _: Any = Depends(get_current_admin),
) -> SiteModelTestResult:
    """Probe one site model with the supplied request settings."""
    return await run_site_model_probe(payload, request)


async def sync_channel_models(
    payload: ChannelModelSyncRequest, _: Any = Depends(get_current_admin)
) -> ChannelModelSyncResponse:
    """Add new upstream models to sync-enabled sites and flag vanished ones."""
    from ..tasks.model_sync import sync_channel_models as run_channel_model_sync

    return await run_channel_model_sync(app_state, site_ids=payload.site_ids)


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
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Credential not found") from exc
    except CredentialRateNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CredentialRateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CredentialRateSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
