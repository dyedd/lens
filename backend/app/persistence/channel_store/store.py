from __future__ import annotations

import uuid

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
from app.persistence.entities import (
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteCredentialRateEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigCredentialEntity,
    SiteProtocolConfigEntity,
)
from app.persistence.protocol_serialization import parse_supported_protocols

from .import_sites import build_site_batch_import_result, prepare_site_batch
from .mapping import SiteChannelProjectionMixin, SiteConfigLoadersMixin
from .write import SiteConfigUpsertsMixin


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
                enabled=item.enabled,
                sort_order=index,
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
            if not credential.enabled:
                raise ValueError(
                    f"Credential is disabled for model discovery: {credential_id}"
                )
            previews.append(
                {
                    "credential_id": credential.id,
                    "credential_name": credential.name,
                }
            )
        return previews

    async def replace_protocol_config_synced_models(
        self,
        protocol_config_id: str,
        credential_id: str,
        protocol: ProtocolKind,
        model_names: list[str],
    ) -> None:
        """Replace one credential/protocol target's synchronized models."""
        async with self._session_factory() as session:
            entity = await session.get(SiteProtocolConfigEntity, protocol_config_id)
            if entity is None:
                raise ResourceNotFoundError(protocol_config_id)
            association = (
                await session.execute(
                    select(SiteProtocolConfigCredentialEntity.id).where(
                        SiteProtocolConfigCredentialEntity.protocol_config_id
                        == protocol_config_id,
                        SiteProtocolConfigCredentialEntity.credential_id
                        == credential_id,
                    )
                )
            ).scalar_one_or_none()
            if association is None:
                raise ValueError(
                    "Credential is not bound to protocol config "
                    f"{protocol_config_id}: {credential_id}"
                )

            protocols = parse_supported_protocols(entity.protocols_json)
            if protocol not in protocols:
                raise ValueError(
                    "Protocol is not enabled in protocol config "
                    f"{protocol_config_id}: {protocol.value}"
                )

            target_rows = (
                (
                    await session.execute(
                        select(SiteDiscoveredModelEntity).where(
                            SiteDiscoveredModelEntity.protocol_config_id
                            == protocol_config_id,
                            SiteDiscoveredModelEntity.credential_id == credential_id,
                            SiteDiscoveredModelEntity.protocol == protocol.value,
                        )
                    )
                )
                .scalars()
                .all()
            )
            manual_names = {
                row.model_name
                for row in target_rows
                if row.source == ModelSource.MANUAL.value
            }
            synced_by_name = {
                row.model_name: row
                for row in target_rows
                if row.source == ModelSource.SYNCED.value
            }
            desired_names = set(model_names) - manual_names
            stale_ids = [
                row.id
                for name, row in synced_by_name.items()
                if name not in desired_names
            ]
            if stale_ids:
                await session.execute(
                    delete(SiteDiscoveredModelEntity).where(
                        SiteDiscoveredModelEntity.id.in_(stale_ids)
                    )
                )

            all_rows = (
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
            next_sort_order = max((row.sort_order for row in all_rows), default=-1) + 1
            for model_name in sorted(desired_names - set(synced_by_name)):
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

            await self._cleanup_invalid_group_items(session, {protocol_config_id})
            await session.commit()


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
        await self._upsert_site_payload(
            session,
            site_id,
            payload.name,
            enabled,
            payload.tags,
            payload.base_urls,
            payload.credentials,
            payload.protocols,
        )

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
                    site_payload.name,
                    prepared_item.enabled,
                    site_payload.tags,
                    site_payload.base_urls,
                    site_payload.credentials,
                    site_payload.protocols,
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
            await session.commit()
        return await self.get_site(site_id)
