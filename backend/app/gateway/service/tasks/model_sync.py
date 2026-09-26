from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

from fastapi import HTTPException

from ....core.errors import ResourceNotFoundError
from ....core.runtime_channel_ids import protocol_config_id_from_runtime_channel_id
from ....models.channels import (
    ChannelConfig,
    ChannelModelSyncResponse,
    ChannelModelSyncResultItem,
)
from ....models.protocols import ChannelModelSyncStatus
from ....models.sites import SiteConfig, SiteProtocolConfig
from ..app_state import logger
from .model_discovery import fetch_upstream_models

if TYPE_CHECKING:
    from ..app_state import AppState


def _compile_model_sync_pattern(pattern: str) -> re.Pattern[str] | None:
    return re.compile(pattern, re.IGNORECASE) if pattern.strip() else None


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
    state: AppState, *, site_ids: list[str] | None = None
) -> ChannelModelSyncResponse:
    """Add new upstream models to sync-enabled sites and flag vanished ones."""
    requested_site_ids = set(site_ids) if site_ids is not None else None
    items: list[ChannelModelSyncResultItem] = []
    for site in await state.channel_store.list_sites():
        if not (site.enabled and site.model_sync_enabled):
            continue
        if requested_site_ids is not None and site.id not in requested_site_ids:
            continue
        items.extend(await _sync_site_models(state, site))

    logger.info(
        "Channel model sync: targets=%s updated=%s failed=%s",
        len(items),
        sum(item.status == ChannelModelSyncStatus.UPDATED for item in items),
        sum(item.status == ChannelModelSyncStatus.FAILED for item in items),
    )
    return ChannelModelSyncResponse(items=items)


async def _sync_site_models(
    state: AppState, site: SiteConfig
) -> list[ChannelModelSyncResultItem]:
    include = _compile_model_sync_pattern(site.model_sync_include)
    exclude = _compile_model_sync_pattern(site.model_sync_exclude)
    credential_names = {
        credential.id: credential.name for credential in site.credentials
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
                    state, protocol_config, channels, item, include, exclude
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
    include: re.Pattern[str] | None,
    exclude: re.Pattern[str] | None,
) -> None:
    # Protocols of one config share a base URL, so one catalog fetch serves all.
    fetch_channel = next(
        (
            credential_channel
            for channel in channels
            if (
                credential_channel := channel_for_credential(
                    channel, item.credential_id
                )
            )
        ),
        None,
    )
    if fetch_channel is None:
        raise ValueError("no usable credential for model discovery")
    upstream_names = set(await fetch_upstream_models(fetch_channel))
    if not upstream_names:
        raise ValueError("upstream returned no models")

    changes = await state.channel_store.sync_upstream_models(
        protocol_config.id,
        item.credential_id,
        [channel.protocol for channel in channels],
        upstream_names=upstream_names,
        wanted_names={
            name
            for name in upstream_names
            if (include is None or include.search(name))
            and (exclude is None or not exclude.search(name))
        },
    )
    item.added = changes.added
    item.missing = changes.missing
    item.restored = changes.restored
    if changes.added or changes.missing or changes.restored:
        item.status = ChannelModelSyncStatus.UPDATED
