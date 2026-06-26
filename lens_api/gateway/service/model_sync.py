from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

from ...core.runtime_channel_ids import protocol_config_id_from_runtime_channel_id
from ...models import (
    ChannelModelSyncGroupChange,
    ChannelModelSyncResponse,
    ChannelModelSyncResultItem,
    ModelGroup,
    ModelGroupEnsureFromSiteRequest,
    ModelGroupEnsureModelInput,
    ModelGroupSyncFilterMode,
    ProtocolKind,
    SiteConfig,
    SiteProtocolConfig,
)
from .runtime_context import ChannelConfig, HTTPException, logger
from .upstream_http import _fetch_upstream_models

if TYPE_CHECKING:
    from .runtime_context import AppState


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


def _group_changes_for_added(
    groups: list[ModelGroup],
    protocol_config: SiteProtocolConfig,
    added_protocols_by_model: dict[str, set[ProtocolKind]],
) -> tuple[list[ChannelModelSyncGroupChange], list[ModelGroupEnsureModelInput]]:
    changes: list[ChannelModelSyncGroupChange] = []
    ensure_inputs: list[ModelGroupEnsureModelInput] = []
    for group in groups:
        if group.route_group_id.strip():
            continue
        if group.sync_filter_mode == ModelGroupSyncFilterMode.NONE:
            continue
        for model_name, model_protocols in added_protocols_by_model.items():
            target_protocols = [p for p in group.protocols if p in model_protocols]
            if not target_protocols:
                continue
            if not _model_matches_sync_filter(
                model_name, group.sync_filter_mode, group.sync_filter_query
            ):
                continue
            changes.append(
                ChannelModelSyncGroupChange(
                    group_name=group.name, model_name=model_name
                )
            )
            ensure_inputs.append(
                ModelGroupEnsureModelInput(
                    protocol_config_id=protocol_config.id,
                    credential_id=protocol_config.credential_id,
                    model_name=model_name,
                    group_name=group.name,
                    protocols=target_protocols,
                )
            )
    return changes, ensure_inputs


def _skipped_item(
    protocol_config_id: str, channel_name: str, error: str
) -> ChannelModelSyncResultItem:
    return ChannelModelSyncResultItem(
        protocol_config_id=protocol_config_id,
        channel_name=channel_name,
        success=False,
        error=error,
    )


async def sync_channel_models(
    state: "AppState", *, dry_run: bool
) -> ChannelModelSyncResponse:
    sites = await state.channel_store.list_sites()
    groups = await state.group_repo.list_groups()
    items: list[ChannelModelSyncResultItem] = []
    synced = 0
    skipped = 0

    for site in sites:
        channels_by_config = _channels_by_protocol_config(state, site)
        ensure_inputs_by_site: list[ModelGroupEnsureModelInput] = []
        for protocol_config in site.protocols:
            if not protocol_config.auto_sync_enabled or not protocol_config.enabled:
                continue

            if not protocol_config.credential_id:
                skipped += 1
                items.append(
                    _skipped_item(
                        protocol_config.id,
                        site.name,
                        "protocol config has no bound credential",
                    )
                )
                continue

            channels = channels_by_config.get(protocol_config.id, [])
            if not channels:
                skipped += 1
                items.append(
                    _skipped_item(
                        protocol_config.id,
                        site.name,
                        "no usable credential for model discovery",
                    )
                )
                continue

            new_names_by_protocol: dict[ProtocolKind, list[str]] = {}
            fetch_error: str | None = None
            for channel in channels:
                try:
                    new_names_by_protocol[channel.protocol] = (
                        await _fetch_upstream_models(channel)
                    )
                except HTTPException as exc:
                    fetch_error = f"[{channel.protocol.value}] {exc.detail}"
                    break
            if fetch_error is not None:
                skipped += 1
                items.append(_skipped_item(protocol_config.id, site.name, fetch_error))
                continue

            old_names_by_protocol: dict[ProtocolKind, set[str]] = defaultdict(set)
            for model in protocol_config.models:
                if model.protocol is not None:
                    old_names_by_protocol[model.protocol].add(model.model_name)

            added: set[str] = set()
            removed: set[str] = set()
            added_protocols_by_model: dict[str, set[ProtocolKind]] = defaultdict(set)
            for protocol, names in new_names_by_protocol.items():
                new_set = set(names)
                old_set = old_names_by_protocol.get(protocol, set())
                for name in new_set - old_set:
                    added.add(name)
                    added_protocols_by_model[name].add(protocol)
                removed.update(old_set - new_set)

            changes, ensure_inputs = _group_changes_for_added(
                groups, protocol_config, added_protocols_by_model
            )

            if not dry_run and (added or removed):
                await state.channel_store.replace_protocol_config_models(
                    protocol_config.id,
                    {p: list(names) for p, names in new_names_by_protocol.items()},
                )
            if not dry_run and ensure_inputs:
                ensure_inputs_by_site.extend(ensure_inputs)

            synced += 1
            items.append(
                ChannelModelSyncResultItem(
                    protocol_config_id=protocol_config.id,
                    channel_name=site.name,
                    success=True,
                    added=sorted(added),
                    removed=sorted(removed),
                    group_added=changes,
                )
            )

        if not dry_run and ensure_inputs_by_site:
            try:
                await state.group_repo.ensure_groups_from_site(
                    ModelGroupEnsureFromSiteRequest(
                        site_id=site.id,
                        dry_run=False,
                        models=ensure_inputs_by_site,
                    )
                )
            except Exception:
                logger.exception(
                    "Channel model sync: ensure groups failed for site %s", site.id
                )

    return ChannelModelSyncResponse(
        dry_run=dry_run,
        synced_channel_count=synced,
        skipped_channel_count=skipped,
        items=items,
    )
