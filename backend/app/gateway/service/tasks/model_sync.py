from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException

from ....core.errors import ResourceNotFoundError
from ....core.model_names import ModelPatternKind, classify_model_pattern
from ....core.model_protocols import ENDPOINT_KIND_PROTOCOLS, resolve_onboard_protocol
from ....core.runtime_channel_ids import protocol_config_id_from_runtime_channel_id
from ....models.channels import (
    ChannelConfig,
    ChannelModelSyncResponse,
    ChannelModelSyncResultItem,
)
from ....models.model_groups import ModelGroupReconcileReport
from ....models.protocols import ChannelModelSyncStatus
from ....models.sites import SiteConfig, SiteProtocolConfig
from ..app_state import logger
from .model_discovery import NATIVE_LISTING_PROTOCOLS, fetch_upstream_models

if TYPE_CHECKING:
    from ..app_state import AppState


def channel_for_credential(
    channel: ChannelConfig, credential_id: str
) -> ChannelConfig | None:
    key = next((item for item in channel.keys if item.id == credential_id), None)
    if key is None:
        return None
    return channel.model_copy(
        update={
            "api_key": key.key,
            "keys": [key],
            "models": [
                model
                for model in channel.models
                if model.credential_id == credential_id
            ],
        }
    )


async def sync_channel_models(
    state: AppState,
    *,
    site_ids: list[str] | None = None,
    credential_ids: list[str] | None = None,
) -> ChannelModelSyncResponse:
    """Run the model pipeline for enabled sites and record the run.

    Discovery, filtering, and storage run per credential; grouping, member
    writes, and retirement then run once over every group, so the record
    shows where each new or vanished model ended up.
    """
    started_at = datetime.now(UTC)
    requested_site_ids = set(site_ids) if site_ids is not None else None
    requested_credential_ids = (
        set(credential_ids) if credential_ids is not None else None
    )
    sites = [
        site
        for site in await state.channel_store.list_sites()
        if site.enabled
        and (requested_site_ids is None or site.id in requested_site_ids)
    ]
    items: list[ChannelModelSyncResultItem] = []
    for site in sites:
        items.extend(await _sync_site_models(state, site, requested_credential_ids))

    logger.info(
        "Channel model sync: targets=%s updated=%s failed=%s",
        len(items),
        sum(item.status == ChannelModelSyncStatus.UPDATED for item in items),
        sum(item.status == ChannelModelSyncStatus.FAILED for item in items),
    )
    groups = await _reconcile_synced_groups(state, items)
    run = ChannelModelSyncResponse(
        started_at=started_at,
        finished_at=datetime.now(UTC),
        items=items,
        groups=groups,
    )
    if not items and not groups.has_changes:
        return run
    return await state.model_sync_run_repo.create_run(run)


async def _reconcile_synced_groups(
    state: AppState, items: list[ChannelModelSyncResultItem]
) -> ModelGroupReconcileReport:
    try:
        report = await state.group_repo.reconcile_group_members()
    except Exception:
        logger.exception("Model group reconcile after model sync failed")
        return ModelGroupReconcileReport()
    logger.info(
        "Model sync groups: added=%s created=%s pending=%s removed=%s",
        len(report.added),
        len(report.created_groups),
        len(report.pending),
        len(report.removed),
    )
    return report


async def _sync_site_models(
    state: AppState,
    site: SiteConfig,
    requested_credential_ids: set[str] | None = None,
) -> list[ChannelModelSyncResultItem]:
    credential_names = {
        credential.id: credential.name for credential in site.credentials
    }
    credential_patterns = {
        credential.id: credential.model_pattern for credential in site.credentials
    }
    channels_by_config: dict[str, list[ChannelConfig]] = defaultdict(list)
    for channel in state.channel_store.flatten_site(site):
        channels_by_config[
            protocol_config_id_from_runtime_channel_id(channel.id)
        ].append(channel)

    items: list[ChannelModelSyncResultItem] = []
    for protocol_config in site.protocols:
        channels = channels_by_config.get(protocol_config.id, [])
        for credential_id in protocol_config.credential_ids:
            if (
                requested_credential_ids is not None
                and credential_id not in requested_credential_ids
            ):
                continue
            item = ChannelModelSyncResultItem(
                site_id=site.id,
                site_name=site.name,
                protocol_config_id=protocol_config.id,
                credential_id=credential_id,
                credential_name=credential_names.get(credential_id, ""),
                status=ChannelModelSyncStatus.UNCHANGED,
            )
            items.append(item)
            try:
                await _sync_credential_models(
                    state,
                    protocol_config,
                    channels,
                    item,
                    credential_patterns,
                )
            except (HTTPException, ResourceNotFoundError, ValueError) as exc:
                item.status = ChannelModelSyncStatus.FAILED
                item.error = (
                    str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
                )
    return items


async def _sync_credential_models(
    state: AppState,
    protocol_config: SiteProtocolConfig,
    channels: list[ChannelConfig],
    item: ChannelModelSyncResultItem,
    credential_patterns: dict[str, str],
) -> None:
    # Protocols of one config share a base URL, so one catalog fetch serves all.
    pattern = credential_patterns.get(item.credential_id, "").strip()
    if not pattern:
        return
    if classify_model_pattern(pattern) is ModelPatternKind.INVALID:
        raise ValueError("invalid model pattern")
    credential_channels = [
        credential_channel
        for channel in channels
        if (credential_channel := channel_for_credential(channel, item.credential_id))
    ]
    # Per-model protocols mix channels on one URL; the OpenAI-compatible list
    # suits every relay, so native Anthropic or Gemini lists only go last.
    fetch_channel = min(
        credential_channels,
        key=lambda channel: channel.protocol in NATIVE_LISTING_PROTOCOLS,
        default=None,
    )
    if fetch_channel is None:
        raise ValueError("no usable credential for model discovery")
    upstream_models = await fetch_upstream_models(fetch_channel)
    if not upstream_models:
        # An empty catalog is a failed fetch, not proof every model vanished.
        raise ValueError("upstream returned no models")
    # A native Anthropic or Gemini list serves every model on its own protocol.
    pinned = ENDPOINT_KIND_PROTOCOLS.get(fetch_channel.endpoint_kind) or (
        fetch_channel.protocol
        if fetch_channel.protocol in NATIVE_LISTING_PROTOCOLS
        else None
    )
    upstream_names = {model.name for model in upstream_models}
    changes = await state.channel_store.sync_upstream_models(
        protocol_config.id,
        item.credential_id,
        upstream_names=upstream_names,
        upstream_pattern=pattern,
        upstream_context_windows={
            model.name: model.context_window
            for model in upstream_models
            if model.context_window is not None
        },
        upstream_protocols={
            model.name: resolve_onboard_protocol(
                model.name,
                pinned=pinned,
                declared=model.protocols,
                configured=protocol_config.protocols,
            )
            for model in upstream_models
        },
    )
    item.added = changes.added
    item.missing = changes.missing
    item.restored = changes.restored
    if changes.added or changes.missing or changes.restored:
        item.status = ChannelModelSyncStatus.UPDATED
