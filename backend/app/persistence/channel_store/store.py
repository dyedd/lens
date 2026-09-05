from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from app.core.errors import ResourceNotFoundError
from app.models.channels import ChannelConfig
from app.models.site_import import (
    SiteBatchImportItemResult,
    SiteBatchImportRequest,
    SiteBatchImportResult,
)
from app.models.sites import (
    SiteConfig,
    SiteCreate,
    SiteEnabledUpdate,
    SiteUpdate,
)
from app.persistence.entities import SiteEntity

from .loaders import ChannelLoadersMixin
from .site_batch_import import (
    build_site_batch_import_result,
    prepare_site_batch,
)
from .site_operations import ChannelSiteOperationsMixin
from .site_payload_processing import ChannelPayloadProcessingMixin
from .upserts import ChannelUpsertsMixin


class ChannelStore(
    ChannelLoadersMixin,
    ChannelPayloadProcessingMixin,
    ChannelUpsertsMixin,
    ChannelSiteOperationsMixin,
):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_channels(self) -> list[ChannelConfig]:
        """Return all runtime channels flattened from configured sites."""
        sites = await self.list_sites()
        items: list[ChannelConfig] = []
        for site in sites:
            items.extend(self._flatten_site(site))
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
