from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

from fastapi import HTTPException

from ...core.runtime_channel_ids import protocol_config_id_from_runtime_channel_id
from ...models import (
    ChannelConfig,
    ChannelModelSyncGroupChange,
    ChannelModelSyncResponse,
    ChannelModelSyncResultItem,
    ChannelModelSyncStatus,
    ModelGroup,
    ModelGroupEnsureFromSiteRequest,
    ModelGroupEnsureModelInput,
    ModelGroupEnsureResultItem,
    ModelGroupSyncFilterMode,
    ModelSource,
    ProtocolKind,
    SiteConfig,
    SiteProtocolConfig,
)
from .app_state import logger
from .model_discovery import _fetch_upstream_models

if TYPE_CHECKING:
    from .app_state import AppState

GroupTargetKey = tuple[str, str, str, str, tuple[ProtocolKind, ...]]


def _group_target_key(
    item: ModelGroupEnsureModelInput | ModelGroupEnsureResultItem,
) -> GroupTargetKey:
    return (
        item.group_name,
        item.protocol_config_id,
        item.credential_id,
        item.model_name,
        tuple(sorted(item.protocols)),
    )


def _compile_sync_filter_regex(query: str) -> re.Pattern[str] | None:
    pattern = query[4:] if query.startswith("(?i)") else query
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error:
        return None


def _model_matches_sync_filter(
    model_name: str, mode: ModelGroupSyncFilterMode, query: str
) -> bool:
    normalized_query = query.strip()
    if not normalized_query:
        return False
    if mode == ModelGroupSyncFilterMode.REGEX:
        regex = _compile_sync_filter_regex(normalized_query)
        if regex is None:
            return False
        return bool(regex.search(model_name))
    if mode == ModelGroupSyncFilterMode.CONTAINS:
        return normalized_query.lower() in model_name.lower()
    return False


def _channels_by_protocol_config(
    state: "AppState", site: SiteConfig
) -> dict[str, list[ChannelConfig]]:
    grouped: dict[str, list[ChannelConfig]] = defaultdict(list)
    for channel in state.channel_store._flatten_site(site):
        grouped[protocol_config_id_from_runtime_channel_id(channel.id)].append(channel)
    return grouped


def _group_ensure_inputs_for_added(
    groups: list[ModelGroup],
    protocol_config: SiteProtocolConfig,
    credential_id: str,
    protocol: ProtocolKind,
    added_models: set[str],
) -> list[ModelGroupEnsureModelInput]:
    ensure_inputs: list[ModelGroupEnsureModelInput] = []
    for group in groups:
        if group.route_group_id.strip():
            continue
        if group.sync_filter_mode == ModelGroupSyncFilterMode.NONE:
            continue
        if protocol not in group.protocols:
            continue
        for model_name in added_models:
            if not _model_matches_sync_filter(
                model_name, group.sync_filter_mode, group.sync_filter_query
            ):
                continue
            ensure_inputs.append(
                ModelGroupEnsureModelInput(
                    protocol_config_id=protocol_config.id,
                    credential_id=credential_id,
                    model_name=model_name,
                    group_name=group.name,
                    protocols=[protocol],
                )
            )
    return ensure_inputs


def _failed_item(
    site: SiteConfig,
    protocol_config: SiteProtocolConfig,
    credential_id: str,
    credential_name: str,
    protocol: ProtocolKind,
    error: str,
) -> ChannelModelSyncResultItem:
    return ChannelModelSyncResultItem(
        site_id=site.id,
        protocol_config_id=protocol_config.id,
        protocol_config_name=protocol_config.name,
        channel_name=site.name,
        credential_id=credential_id,
        credential_name=credential_name,
        protocol=protocol,
        status=ChannelModelSyncStatus.FAILED,
        error=error,
    )


def _channel_for_credential(
    channel: ChannelConfig, credential_id: str
) -> ChannelConfig | None:
    key = next((item for item in channel.keys if item.id == credential_id), None)
    if key is None or not key.enabled:
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
    state: "AppState", *, dry_run: bool
) -> ChannelModelSyncResponse:
    """Synchronize configured channel models and report the resulting changes."""
    sites = await state.channel_store.list_sites()
    groups = await state.group_repo.list_groups()
    items: list[ChannelModelSyncResultItem] = []

    for site in sites:
        if not site.enabled:
            continue
        channels_by_config = _channels_by_protocol_config(state, site)
        credentials_by_id = {
            credential.id: credential for credential in site.credentials
        }
        base_urls_by_id = {base_url.id: base_url for base_url in site.base_urls}
        ensure_inputs_by_site: list[ModelGroupEnsureModelInput] = []
        group_targets_by_key: dict[GroupTargetKey, ChannelModelSyncResultItem] = {}
        for protocol_config in site.protocols:
            if not protocol_config.sync_targets or not protocol_config.enabled:
                continue
            base_url = base_urls_by_id.get(protocol_config.base_url_id)
            if base_url is None or not base_url.enabled:
                continue

            channels = channels_by_config.get(protocol_config.id, [])
            channels_by_protocol = {channel.protocol: channel for channel in channels}
            for credential_id in protocol_config.credential_ids:
                credential = credentials_by_id.get(credential_id)
                if credential is None or not credential.enabled:
                    continue
                for protocol in protocol_config.protocols:
                    target_names = {
                        target.model_name
                        for target in protocol_config.sync_targets
                        if target.credential_id == credential_id
                        and target.protocol == protocol
                    }
                    if not target_names:
                        continue
                    channel = channels_by_protocol.get(protocol)
                    target_channel = (
                        _channel_for_credential(channel, credential_id)
                        if channel is not None
                        else None
                    )
                    if target_channel is None:
                        items.append(
                            _failed_item(
                                site,
                                protocol_config,
                                credential_id,
                                credential.name,
                                protocol,
                                "no usable credential for model discovery",
                            )
                        )
                        continue

                    try:
                        all_upstream = await _fetch_upstream_models(target_channel)
                    except HTTPException as exc:
                        items.append(
                            _failed_item(
                                site,
                                protocol_config,
                                credential_id,
                                credential.name,
                                protocol,
                                str(exc.detail),
                            )
                        )
                        continue

                    target_models = [
                        model
                        for model in protocol_config.models
                        if model.credential_id == credential_id
                        and model.protocol == protocol
                    ]
                    old_synced_names = {
                        model.model_name
                        for model in target_models
                        if model.source == ModelSource.SYNCED
                    }
                    all_upstream_set = set(all_upstream)
                    desired_synced = target_names & all_upstream_set
                    status = ChannelModelSyncStatus.UNCHANGED
                    added = desired_synced - old_synced_names
                    removed = old_synced_names - desired_synced
                    ensure_inputs = _group_ensure_inputs_for_added(
                        groups,
                        protocol_config,
                        credential_id,
                        protocol,
                        added,
                    )
                    if added or removed or ensure_inputs:
                        status = ChannelModelSyncStatus.UPDATED
                    if not dry_run and (added or removed):
                        await state.channel_store.replace_protocol_config_synced_models(
                            protocol_config.id,
                            credential_id,
                            protocol,
                            sorted(desired_synced),
                        )
                    if not dry_run and ensure_inputs:
                        ensure_inputs_by_site.extend(ensure_inputs)

                    result_item = ChannelModelSyncResultItem(
                        site_id=site.id,
                        protocol_config_id=protocol_config.id,
                        protocol_config_name=protocol_config.name,
                        channel_name=site.name,
                        credential_id=credential_id,
                        credential_name=credential.name,
                        protocol=protocol,
                        status=status,
                        added=sorted(added),
                        removed=sorted(removed),
                        group_added=[
                            ChannelModelSyncGroupChange(
                                group_name=ensure_input.group_name,
                                model_name=ensure_input.model_name,
                            )
                            for ensure_input in ensure_inputs
                        ],
                    )
                    items.append(result_item)
                    for ensure_input in ensure_inputs:
                        group_targets_by_key[_group_target_key(ensure_input)] = (
                            result_item
                        )

        if not dry_run and ensure_inputs_by_site:
            try:
                ensure_result = await state.group_repo.ensure_groups_from_site(
                    ModelGroupEnsureFromSiteRequest(
                        site_id=site.id,
                        dry_run=False,
                        models=ensure_inputs_by_site,
                    )
                )
            except Exception:
                for target in group_targets_by_key.values():
                    target.group_added = []
                    target.warning = "automatic model group update failed"
                logger.exception(
                    "Channel model sync: ensure groups failed for site %s", site.id
                )
            else:
                for target in group_targets_by_key.values():
                    target.group_added = []
                for ensure_item in ensure_result.items:
                    if ensure_item.status not in {"create", "update"}:
                        continue
                    target = group_targets_by_key.get(_group_target_key(ensure_item))
                    if target is not None and ensure_item.added_count:
                        target.group_added.append(
                            ChannelModelSyncGroupChange(
                                group_name=ensure_item.group_name,
                                model_name=ensure_item.model_name,
                            )
                        )

    counts = defaultdict(int)
    for item in items:
        counts[item.status] += 1
    result = ChannelModelSyncResponse(
        dry_run=dry_run,
        eligible_target_count=len(items),
        updated_target_count=counts[ChannelModelSyncStatus.UPDATED],
        unchanged_target_count=counts[ChannelModelSyncStatus.UNCHANGED],
        failed_target_count=counts[ChannelModelSyncStatus.FAILED],
        items=items,
    )
    logger.info(
        "Channel model sync: targets=%s updated=%s unchanged=%s failed=%s",
        result.eligible_target_count,
        result.updated_target_count,
        result.unchanged_target_count,
        result.failed_target_count,
    )
    return result
