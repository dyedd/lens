from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, Response

from ....models import (
    ChannelConfig,
    ChannelModelSyncRequest,
    ChannelModelSyncResponse,
    ProtocolKind,
    SiteBatchImportRequest,
    SiteBatchImportResult,
    SiteConfig,
    SiteCreate,
    SiteCredential,
    SiteEnabledUpdate,
    SiteModelFetchItem,
    SiteModelFetchRequest,
    SiteModelGroupSaveRequest,
    SiteModelGroupSaveResponse,
    SiteModelTestRequest,
    SiteModelTestResult,
    ModelGroupEnsureFromSiteRequest,
    ModelGroupEnsureModelInput,
    SiteRuntimeSummary,
    SiteUpdate,
)
from ..auth import get_current_admin
from ..site_model_probe import run_site_model_probe
from ..app_state import app_state
from ..model_discovery import _fetch_upstream_models
from ..model_discovery import filter_model_names
from ..upstream_support import _format_channel_error


async def list_sites(
    tag: str | None = None, _: Any = Depends(get_current_admin)
) -> list[SiteConfig]:
    """List configured upstream sites."""
    return await app_state.channel_store.list_sites(tag=tag)


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


def _suggest_model_group_name(model_name: str, existing_names: Iterable[str]) -> str:
    normalized_model_name = model_name.strip()
    if not normalized_model_name:
        return ""

    comparable_model_name = normalized_model_name.casefold()
    best_match = ""
    for name in existing_names:
        normalized_group_name = name.strip()
        if len(normalized_group_name) <= len(best_match):
            continue
        comparable_group_name = normalized_group_name.casefold()
        if (
            comparable_group_name not in comparable_model_name
            and comparable_model_name not in comparable_group_name
        ):
            continue
        best_match = normalized_group_name
    return best_match or normalized_model_name


def _build_model_group_inputs(
    site: SiteConfig,
    existing_group_names: Iterable[str],
    grouped_model_keys: set[tuple[str, str, str]],
) -> list[ModelGroupEnsureModelInput]:
    group_names = [name.strip() for name in existing_group_names if name.strip()]
    enabled_base_urls = {item.id for item in site.base_urls if item.enabled}
    enabled_credentials = {item.id for item in site.credentials if item.enabled}
    grouped: dict[tuple[str, str, str], ModelGroupEnsureModelInput] = {}

    for protocol_config in site.protocols:
        if (
            not protocol_config.enabled
            or protocol_config.base_url_id not in enabled_base_urls
        ):
            continue
        configured_protocols = set(protocol_config.protocols)
        for model in protocol_config.models:
            model_name = model.model_name.strip()
            if (
                not model.enabled
                or not model_name
                or model.protocol is None
                or model.protocol not in configured_protocols
                or model.credential_id not in enabled_credentials
            ):
                continue
            key = (
                protocol_config.id,
                model.credential_id,
                model_name,
            )
            if key in grouped_model_keys:
                continue
            current = grouped.get(key)
            if current is None:
                grouped[key] = ModelGroupEnsureModelInput(
                    protocol_config_id=protocol_config.id,
                    credential_id=model.credential_id,
                    model_name=model_name,
                    group_name=_suggest_model_group_name(model_name, group_names),
                    protocols=[model.protocol],
                )
            elif model.protocol not in current.protocols:
                current.protocols.append(model.protocol)
    return list(grouped.values())


async def _save_site_with_model_groups(
    site_id: str | None,
    payload: SiteModelGroupSaveRequest,
    *,
    creating: bool,
) -> SiteModelGroupSaveResponse:
    next_site_id = site_id or str(uuid4())
    async with app_state.session_factory() as session:
        await app_state.channel_store.save_site_in_session(
            session,
            next_site_id,
            payload,
            creating=creating,
        )
        await session.flush()
        saved_site = await app_state.channel_store.get_site_in_session(
            session, next_site_id
        )
        group_names = await app_state.group_repo.list_execution_group_names_in_session(
            session
        )
        grouped_model_keys = (
            await app_state.group_repo.list_grouped_model_keys_in_session(session)
        )
        models = payload.models
        if models is None:
            models = _build_model_group_inputs(
                saved_site, group_names, grouped_model_keys
            )
        group_result = await app_state.group_repo.ensure_groups_from_site_in_session(
            session,
            ModelGroupEnsureFromSiteRequest(
                site_id=next_site_id,
                dry_run=payload.dry_run,
                allow_protocol_extension=payload.allow_protocol_extension,
                models=models,
            ),
        )
        if payload.dry_run:
            await session.rollback()
        else:
            await session.commit()
    return SiteModelGroupSaveResponse(site=saved_site, model_groups=group_result)


async def create_site_with_model_groups(
    payload: SiteModelGroupSaveRequest, _: Any = Depends(get_current_admin)
) -> SiteModelGroupSaveResponse:
    """Preview or atomically create a site and its automatic model groups."""
    return await _save_site_with_model_groups(payload.site_id, payload, creating=True)


async def update_site_with_model_groups(
    site_id: str,
    payload: SiteModelGroupSaveRequest,
    _: Any = Depends(get_current_admin),
) -> SiteModelGroupSaveResponse:
    """Preview or atomically update a site and its automatic model groups."""
    return await _save_site_with_model_groups(site_id, payload, creating=False)


async def update_site_enabled(
    site_id: str,
    payload: SiteEnabledUpdate,
    _: Any = Depends(get_current_admin),
) -> SiteConfig:
    """Update an upstream site's master enabled state."""
    return await app_state.channel_store.update_site_enabled(site_id, payload)


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
        )
        try:
            model_names = filter_model_names(
                await _fetch_upstream_models(channel), payload.match_regex
            )
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
    payload: SiteModelTestRequest,
    request: Request,
    _: Any = Depends(get_current_admin),
) -> SiteModelTestResult:
    """Probe one site model with the supplied request settings."""
    return await run_site_model_probe(payload, request)


async def sync_channel_models(
    payload: ChannelModelSyncRequest, _: Any = Depends(get_current_admin)
) -> ChannelModelSyncResponse:
    """Synchronize stored channel models with their upstream sites."""
    from ..model_sync import sync_channel_models as run_channel_model_sync

    return await run_channel_model_sync(app_state, dry_run=payload.dry_run)


async def sync_site_credential_rate(
    site_id: str,
    credential_id: str,
    _: Any = Depends(get_current_admin),
) -> SiteCredential:
    """Synchronize one configured upstream credential rate."""
    from ..credential_rate_tasks import (
        CredentialRateConflictError,
        CredentialRateSyncError,
        CredentialRateNotConfiguredError,
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
