from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
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
from .model_group_placement import run_model_group_placement

if TYPE_CHECKING:
    from ..app_state import AppState


def _build_model_sync_filter(
    site: SiteConfig, rule_patterns: dict[str, re.Pattern[str]]
) -> Callable[[str], bool]:
    """Build a predicate for models matching any include rule and no exclude rule."""
    include = [
        rule_patterns[rule_id]
        for rule_id in site.model_sync_include_rule_ids
        if rule_id in rule_patterns
    ]
    exclude = [
        rule_patterns[rule_id]
        for rule_id in site.model_sync_exclude_rule_ids
        if rule_id in rule_patterns
    ]

    def is_wanted(model_name: str) -> bool:
        return (
            not site.model_sync_include_rule_ids
            or any(pattern.search(model_name) for pattern in include)
        ) and not any(pattern.search(model_name) for pattern in exclude)

    return is_wanted


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
    sites = [
        site
        for site in await state.channel_store.list_sites()
        if site.enabled
        and site.model_sync_enabled
        and (requested_site_ids is None or site.id in requested_site_ids)
    ]
    rule_patterns = await state.regex_rule_repo.load_patterns(
        rule_id
        for site in sites
        for rule_id in (
            *site.model_sync_include_rule_ids,
            *site.model_sync_exclude_rule_ids,
        )
    )
    items: list[ChannelModelSyncResultItem] = []
    for site in sites:
        items.extend(
            await _sync_site_models(
                state, site, _build_model_sync_filter(site, rule_patterns)
            )
        )

    logger.info(
        "Channel model sync: targets=%s updated=%s failed=%s",
        len(items),
        sum(item.status == ChannelModelSyncStatus.UPDATED for item in items),
        sum(item.status == ChannelModelSyncStatus.FAILED for item in items),
    )
    await run_model_group_placement(state)
    return ChannelModelSyncResponse(items=items)


async def _sync_site_models(
    state: AppState, site: SiteConfig, is_wanted: Callable[[str], bool]
) -> list[ChannelModelSyncResultItem]:
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
                    state, protocol_config, channels, item, is_wanted
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
    is_wanted: Callable[[str], bool],
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
        wanted_names={name for name in upstream_names if is_wanted(name)},
    )
    item.added = changes.added
    item.missing = changes.missing
    item.restored = changes.restored
    if changes.added or changes.missing or changes.restored:
        item.status = ChannelModelSyncStatus.UPDATED
