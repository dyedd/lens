from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException

from ....core.errors import ModelDiscoveryError, ResourceNotFoundError
from ....core.model_endpoints import resolve_model_base_url_id
from ....core.model_names import ModelPatternKind, classify_model_pattern
from ....core.model_protocols import ENDPOINT_KIND_PROTOCOLS, resolve_onboard_protocol
from ....core.runtime_channel_ids import protocol_config_id_from_runtime_channel_id
from ....models.channels import (
    ChannelConfig,
    ChannelModelSyncResponse,
    ChannelModelSyncResultItem,
)
from ....models.model_groups import ModelGroupReconcileReport
from ....models.protocols import ChannelModelSyncStatus, ProtocolKind
from ....models.sites import SiteConfig, SiteProtocolConfig
from ..app_state import logger
from .model_discovery import (
    NATIVE_LISTING_PROTOCOLS,
    UpstreamModel,
    fetch_upstream_models,
)

if TYPE_CHECKING:
    from ..app_state import AppState


@dataclass(frozen=True, slots=True)
class _ModelCatalog:
    models: list[UpstreamModel]
    protocols: dict[str, ProtocolKind]
    existing_protocols: dict[str, frozenset[ProtocolKind]]


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
    report = await state.group_repo.reconcile_group_members()
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

    catalogs: dict[str, _ModelCatalog] = {}
    base_urls = {url.id: url for url in site.base_urls}
    configs = sorted(
        site.protocols,
        key=lambda config: (
            base_urls[config.base_url_id].kind not in {"china", "default"},
            base_urls[config.base_url_id].kind != "china",
        ),
    )
    items: list[ChannelModelSyncResultItem] = []
    for protocol_config in configs:
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
                catalog = await _sync_credential_models(
                    state,
                    protocol_config,
                    channels,
                    item,
                    credential_patterns,
                    site=site,
                    catalog=catalogs.get(credential_id),
                )
                if catalog is not None and base_urls[
                    protocol_config.base_url_id
                ].kind in {"default", "china", "protocol"}:
                    catalogs[credential_id] = catalog
            except (
                HTTPException,
                ModelDiscoveryError,
                ResourceNotFoundError,
                ValueError,
            ) as exc:
                item.status = ChannelModelSyncStatus.FAILED
                item.error = str(
                    exc.detail
                    if isinstance(exc, HTTPException)
                    else exc.public_message
                    if isinstance(exc, ModelDiscoveryError)
                    else exc
                )
    return items


async def _sync_credential_models(
    state: AppState,
    protocol_config: SiteProtocolConfig,
    channels: list[ChannelConfig],
    item: ChannelModelSyncResultItem,
    credential_patterns: dict[str, str],
    *,
    site: SiteConfig,
    catalog: _ModelCatalog | None,
) -> _ModelCatalog | None:
    pattern = credential_patterns.get(item.credential_id, "").strip()
    if not pattern:
        return None
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
    if catalog is None:
        # 通用目录失败时保留旧模型，不能改用专用地址把全目录锁为单一协议。
        if fetch_channel.endpoint_kind not in {"default", "china", "protocol"} and any(
            url.kind in {"default", "china", "protocol"}
            and any(
                config.base_url_id == url.id
                and item.credential_id in config.credential_ids
                for config in site.protocols
            )
            for url in site.base_urls
        ):
            raise ValueError("no usable shared model catalog")
        upstream_models = await fetch_upstream_models(fetch_channel)
        if not upstream_models:
            raise ValueError("upstream returned no models")
        pinned = ENDPOINT_KIND_PROTOCOLS.get(fetch_channel.endpoint_kind) or (
            fetch_channel.protocol
            if fetch_channel.protocol in NATIVE_LISTING_PROTOCOLS
            else None
        )
        existing_protocols: dict[str, set[ProtocolKind]] = defaultdict(set)
        for config in site.protocols:
            for model in config.models:
                if (
                    model.credential_id == item.credential_id
                    and model.protocol is not None
                ):
                    existing_protocols[model.model_name].add(model.protocol)
        preferred_protocols = {
            name: sorted(protocols, key=lambda protocol: protocol.value)[0]
            for name, protocols in existing_protocols.items()
        }
        protocols = {
            model.name: preferred_protocols.get(model.name)
            or resolve_onboard_protocol(
                model.name,
                pinned=pinned,
                declared=model.protocols,
                configured=protocol_config.protocols,
            )
            for model in upstream_models
        }
        catalog = _ModelCatalog(
            models=upstream_models,
            protocols=protocols,
            existing_protocols={
                name: frozenset(protocols)
                for name, protocols in existing_protocols.items()
            },
        )
    upstream_models, protocols = catalog.models, catalog.protocols
    upstream_names: set[str] = set()
    for model in upstream_models:
        existing_protocols = catalog.existing_protocols.get(model.name)
        if existing_protocols:
            matches_endpoint = any(
                resolve_model_base_url_id(
                    site.base_urls,
                    site.credentials,
                    item.credential_id,
                    protocol,
                )
                == protocol_config.base_url_id
                for protocol in existing_protocols
            )
        else:
            matches_endpoint = (
                resolve_model_base_url_id(
                    site.base_urls,
                    site.credentials,
                    item.credential_id,
                    protocols[model.name],
                )
                == protocol_config.base_url_id
            )
        if matches_endpoint:
            upstream_names.add(model.name)
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
        upstream_protocols=protocols,
    )
    item.added = changes.added
    item.missing = changes.missing
    item.restored = changes.restored
    if changes.added or changes.missing or changes.restored:
        item.status = ChannelModelSyncStatus.UPDATED
    return catalog
