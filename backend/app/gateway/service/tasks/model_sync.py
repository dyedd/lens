from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ....core.errors import ModelDiscoveryError, ResourceNotFoundError
from ....core.model_protocols import ENDPOINT_KIND_PROTOCOLS
from ....core.runtime_channel_ids import compose_runtime_channel_id
from ....models.channels import (
    ChannelConfig,
    ChannelModelSyncResponse,
    ChannelModelSyncResultItem,
)
from ....models.model_groups import ModelGroupReconcileReport
from ....models.protocols import ChannelModelSyncStatus, ProtocolKind
from ....models.sites import SiteBaseUrl, SiteConfig, SiteCredential, SiteProtocolConfig
from ..app_state import logger
from .model_discovery import (
    UpstreamModelList,
    fetch_upstream_model_list,
)

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
    """Refresh saved models per credential, update groups, and record the run."""
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
    groups = await _reconcile_synced_groups(state)
    run = ChannelModelSyncResponse(
        started_at=started_at,
        finished_at=datetime.now(UTC),
        items=items,
        groups=groups,
    )
    if not items and not groups.has_changes:
        return run
    return await state.model_sync_run_repo.create_run(run)


async def _reconcile_synced_groups(state: AppState) -> ModelGroupReconcileReport:
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
    credentials = {credential.id: credential for credential in site.credentials}
    base_urls = {url.id: url for url in site.base_urls}
    catalogs: dict[tuple[str, str], UpstreamModelList | ModelDiscoveryError] = {}
    items: list[ChannelModelSyncResultItem] = []
    for config in site.protocols:
        address = base_urls[config.base_url_id]
        if address.kind == "models":
            continue
        for credential_id in config.credential_ids:
            if (
                requested_credential_ids is not None
                and credential_id not in requested_credential_ids
            ):
                continue
            credential = credentials[credential_id]
            item = ChannelModelSyncResultItem(
                site_id=site.id,
                site_name=site.name,
                protocol_config_id=config.id,
                credential_id=credential_id,
                credential_name=credential.name,
                status=ChannelModelSyncStatus.UNCHANGED,
            )
            items.append(item)
            try:
                await _sync_credential_models(
                    state,
                    site,
                    config,
                    credential,
                    address,
                    item,
                    catalogs,
                )
            except (ModelDiscoveryError, ResourceNotFoundError, ValueError) as exc:
                item.status = ChannelModelSyncStatus.FAILED
                item.error = str(exc)
    return items


async def _sync_credential_models(
    state: AppState,
    site: SiteConfig,
    config: SiteProtocolConfig,
    credential: SiteCredential,
    address: SiteBaseUrl,
    item: ChannelModelSyncResultItem,
    catalogs: dict[tuple[str, str], UpstreamModelList | ModelDiscoveryError],
) -> None:
    if not any(model.credential_id == credential.id for model in config.models):
        return
    source = next(
        (
            url
            for url in site.base_urls
            if url.kind == "models"
            and (credential.base_url_ids is None or url.id in credential.base_url_ids)
        ),
        address,
    )
    catalog_key = (source.id, credential.id)
    catalog = catalogs.get(catalog_key)
    if catalog is None:
        listing_protocol = ENDPOINT_KIND_PROTOCOLS.get(
            source.kind, ProtocolKind.OPENAI_CHAT
        )
        channel = ChannelConfig(
            id=compose_runtime_channel_id(config.id, listing_protocol),
            site_id=site.id,
            site_tags=list(site.tags),
            name=site.name,
            protocol=listing_protocol,
            base_url=source.url,
            endpoint_kind=source.kind,
            model_list_url=source.url if source.kind == "models" else None,
            api_key=credential.api_key,
            keys=[
                {
                    "id": credential.id,
                    "key": credential.api_key,
                    "remark": credential.name,
                }
            ],
            headers=site.headers,
            proxy_mode=site.proxy_mode,
            channel_proxy=site.channel_proxy,
        )
        try:
            catalog = await fetch_upstream_model_list(channel)
        except ModelDiscoveryError as exc:
            # Reuse failures so every outlet sees the same catalog result.
            catalogs[catalog_key] = exc
            raise
        catalogs[catalog_key] = catalog
    if isinstance(catalog, ModelDiscoveryError):
        raise catalog

    changes = await state.channel_store.sync_upstream_models(
        config.id,
        credential.id,
        upstream_names={model.name for model in catalog.models},
        upstream_context_windows={
            model.name: model.context_window
            for model in catalog.models
            if model.context_window is not None
        },
    )
    item.added = changes.added
    item.missing = changes.missing
    item.restored = changes.restored
    if changes.added or changes.missing or changes.restored:
        item.status = ChannelModelSyncStatus.UPDATED
