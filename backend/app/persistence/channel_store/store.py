from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from app.core.errors import ResourceNotFoundError
from app.models.channels import ChannelConfig
from app.models.protocols import ModelSource, ProtocolKind
from app.models.site_import import (
    SiteBatchImportItemResult,
    SiteBatchImportRequest,
    SiteBatchImportResult,
)
from app.models.site_model_test import SiteModelFetchRequest
from app.models.sites import (
    SiteConfig,
    SiteCreate,
    SiteCredential,
    SiteEnabledUpdate,
    SiteUpdate,
)
from app.persistence.channel_store.endpoint_credentials import credential_ids_for_url
from app.persistence.entities import (
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteCredentialRateEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)

from .import_sites import build_site_batch_import_result, prepare_site_batch
from .mapping import SiteChannelProjectionMixin, SiteConfigLoadersMixin
from .write import SiteConfigUpsertsMixin


@dataclass(frozen=True, slots=True)
class UpstreamModelChanges:
    added: list[str]
    missing: list[str]
    restored: list[str]


class SiteOperationsMixin:
    async def delete_site(self, site_id: str) -> None:
        """Delete a site and its dependent channel data."""
        async with self._session_factory() as session:
            site = await session.get(SiteEntity, site_id)
            if site is None:
                raise ResourceNotFoundError(site_id)

            protocol_config_ids = await self._site_protocol_config_ids(session, site_id)
            credential_ids = await self._site_credential_ids(session, site_id)
            await self._cleanup_deleted_protocol_configs(
                session, set(protocol_config_ids)
            )
            if credential_ids:
                await session.execute(
                    delete(SiteCredentialRateEntity).where(
                        SiteCredentialRateEntity.credential_id.in_(credential_ids)
                    )
                )
                await session.execute(
                    delete(SiteCredentialEntity).where(
                        SiteCredentialEntity.id.in_(credential_ids)
                    )
                )
            await session.execute(
                delete(SiteBaseUrlEntity).where(SiteBaseUrlEntity.site_id == site_id)
            )
            await session.delete(site)
            await self._cleanup_invalid_group_items(session, set(protocol_config_ids))
            await session.commit()

    async def fetch_models_preview(
        self, payload: SiteModelFetchRequest
    ) -> list[dict[str, str]]:
        """Validate model discovery credentials and return preview entries."""
        credentials = [
            SiteCredential(
                id=item.id or str(uuid.uuid4()),
                name=item.name.strip(),
                api_key=item.api_key,
                sort_order=index,
                base_url_id=item.base_url_id,
            )
            for index, item in enumerate(payload.credentials)
            if item.name.strip() and item.api_key.strip()
        ]
        credential_map = {item.id: item for item in credentials}
        credential_ids = list(dict.fromkeys(payload.credential_ids))
        if not credential_ids:
            raise ValueError("At least one credential is required for model discovery")

        previews: list[dict[str, str]] = []
        for credential_id in credential_ids:
            credential = credential_map.get(credential_id)
            if credential is None:
                raise ValueError(
                    f"Credential not found for model discovery: {credential_id}"
                )
            previews.append(
                {
                    "credential_id": credential.id,
                    "credential_name": credential.name,
                }
            )
        return previews

    async def sync_upstream_models(
        self,
        protocol_config_id: str,
        credential_id: str,
        protocols: list[ProtocolKind],
        *,
        upstream_names: set[str],
        wanted_names: set[str],
    ) -> UpstreamModelChanges:
        """Add wanted upstream models and flag synced models missing upstream."""
        async with self._session_factory() as session:
            entity = await session.get(SiteProtocolConfigEntity, protocol_config_id)
            if entity is None:
                raise ResourceNotFoundError(protocol_config_id)
            credential_rows = (
                (
                    await session.execute(
                        select(SiteCredentialEntity).where(
                            SiteCredentialEntity.site_id == entity.site_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            bound_ids = set(
                credential_ids_for_url(
                    [(row.id, row.base_url_id) for row in credential_rows],
                    entity.base_url_id,
                )
            )
            if credential_id not in bound_ids:
                raise ValueError(
                    "Credential is not bound to protocol config "
                    f"{protocol_config_id}: {credential_id}"
                )

            config_rows = (
                (
                    await session.execute(
                        select(SiteDiscoveredModelEntity).where(
                            SiteDiscoveredModelEntity.protocol_config_id
                            == protocol_config_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            credential_models = [
                row for row in config_rows if row.credential_id == credential_id
            ]
            bound_names = {row.model_name for row in credential_models}
            # Automatic forwarding cannot share a model with fixed protocols.
            added_protocols = (
                [ProtocolKind.AUTO] if ProtocolKind.AUTO in protocols else protocols
            )
            next_sort_order = (
                max((row.sort_order for row in config_rows), default=-1) + 1
            )
            added = sorted(wanted_names - bound_names)
            for model_name in added:
                for protocol in added_protocols:
                    session.add(
                        SiteDiscoveredModelEntity(
                            id=str(uuid.uuid4()),
                            protocol_config_id=protocol_config_id,
                            credential_id=credential_id,
                            model_name=model_name,
                            enabled=1,
                            sort_order=next_sort_order,
                            protocol=protocol.value,
                            source=ModelSource.SYNCED.value,
                        )
                    )
                    next_sort_order += 1

            missing: set[str] = set()
            restored: set[str] = set()
            for row in credential_models:
                if row.source != ModelSource.SYNCED.value:
                    continue
                is_missing = row.model_name not in upstream_names
                if is_missing == bool(row.upstream_missing):
                    continue
                row.upstream_missing = int(is_missing)
                (missing if is_missing else restored).add(row.model_name)

            if added or missing or restored:
                await session.commit()
            return UpstreamModelChanges(
                added=added, missing=sorted(missing), restored=sorted(restored)
            )


class ChannelStore(
    SiteConfigLoadersMixin,
    SiteChannelProjectionMixin,
    SiteConfigUpsertsMixin,
    SiteOperationsMixin,
):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_channels(self) -> list[ChannelConfig]:
        """Return all runtime channels flattened from configured sites."""
        sites = await self.list_sites()
        items: list[ChannelConfig] = []
        for site in sites:
            items.extend(self.flatten_site(site))
        return sorted(items, key=lambda item: (item.name.lower(), item.id))

    async def list_sites(self, tag: str | None = None) -> list[SiteConfig]:
        """Return all configured sites."""
        async with self._session_factory() as session:
            sites = await self._load_sites(session)
        trimmed_tag = tag.strip() if tag else ""
        if not trimmed_tag:
            return sites
        return [site for site in sites if trimmed_tag in site.tags]

    async def get_site(self, site_id: str) -> SiteConfig:
        """Return a site by identifier or raise when it does not exist."""
        async with self._session_factory() as session:
            return await self.get_site_in_session(session, site_id)

    async def get_site_in_session(
        self, session: AsyncSession, site_id: str
    ) -> SiteConfig:
        """Return a site from a caller-owned transaction."""
        sites = await self._load_sites(session, site_ids=[site_id])
        if not sites:
            raise ResourceNotFoundError(site_id)
        return sites[0]

    async def create_site(self, payload: SiteCreate) -> SiteConfig:
        """Create and return a site from the supplied configuration."""
        async with self._session_factory() as session:
            site_id = str(uuid.uuid4())
            await self.save_site_in_session(session, site_id, payload, creating=True)
            await session.commit()
        return await self.get_site(site_id)

    async def save_site_in_session(
        self,
        session: AsyncSession,
        site_id: str,
        payload: SiteCreate | SiteUpdate,
        *,
        creating: bool,
    ) -> None:
        """Create or update a site without committing the caller's transaction."""
        site = await session.get(SiteEntity, site_id)
        if not creating and site is None:
            raise ResourceNotFoundError(site_id)
        if creating and site is not None:
            raise ValueError(f"Site already exists: {site_id}")
        if creating:
            await self._ensure_site_name_unique(session, payload.name)
            enabled = True
        else:
            await self._ensure_site_name_unique(
                session, payload.name, exclude_site_id=site_id
            )
            enabled = bool(site.enabled)
        await self._upsert_site_payload(session, site_id, payload, enabled=enabled)

    async def import_sites(
        self, payload: SiteBatchImportRequest
    ) -> SiteBatchImportResult:
        """Validate and atomically import a batch of site configurations."""
        site_ids: dict[int, str] = {}

        async with self._session_factory() as session:
            existing_names = await self._site_name_keys(session)
            batch = prepare_site_batch(payload.sites, existing_names)
            for index, prepared_item in batch.sites.items():
                site_id = str(uuid.uuid4())
                site_payload = prepared_item.payload
                await self._upsert_site_payload(
                    session,
                    site_id,
                    site_payload,
                    enabled=prepared_item.enabled,
                )
                site_ids[index] = site_id
            if site_ids:
                await session.commit()

        if site_ids:
            created_sites = await self._load_sites_by_ids(list(site_ids.values()))
            sites_by_id = {site.id: site for site in created_sites}
            for index, site_id in site_ids.items():
                site = sites_by_id[site_id]
                batch.item_results[index] = SiteBatchImportItemResult(
                    index=index,
                    name=site.name,
                    status="created",
                    reason="",
                    site=site,
                    errors=[],
                )

        return build_site_batch_import_result(batch.item_results)

    async def update_site(self, site_id: str, payload: SiteUpdate) -> SiteConfig:
        """Replace and return an existing site configuration."""
        async with self._session_factory() as session:
            await self.save_site_in_session(session, site_id, payload, creating=False)
            await session.commit()
        return await self.get_site(site_id)

    async def update_site_enabled(
        self, site_id: str, payload: SiteEnabledUpdate
    ) -> SiteConfig:
        """Update and return a site's master enabled state."""
        async with self._session_factory() as session:
            site = await session.get(SiteEntity, site_id)
            if site is None:
                raise ResourceNotFoundError(site_id)
            site.enabled = int(payload.enabled)
            site.updated_at = datetime.now(UTC).replace(tzinfo=None)
            await session.commit()
        return await self.get_site(site_id)
