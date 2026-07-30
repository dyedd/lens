from __future__ import annotations

from .shared import (
    AsyncSession,
    ChannelConfig,
    ModelGroupItemEntity,
    ProtocolKind,
    SiteBaseUrlEntity,
    SiteBatchImportItemResult,
    SiteBatchImportRequest,
    SiteBatchImportResult,
    SiteConfig,
    SiteCreate,
    SiteCredential,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEnabledUpdate,
    SiteEntity,
    SiteModelFetchRequest,
    SiteModelInput,
    SiteProtocolConfigEntity,
    SiteProtocolConfigInput,
    SiteUpdate,
    async_sessionmaker,
    delete,
    or_,
    select,
    uuid,
)
from .loaders import ChannelLoadersMixin
from .normalization import ChannelNormalizationMixin
from .site_batch_import import (
    build_site_batch_import_result,
    prepare_site_batch,
)
from .site_operations import ChannelSiteOperationsMixin
from .upserts import ChannelUpsertsMixin
from ..shared import _parse_supported_protocols_json


class ChannelStore(
    ChannelLoadersMixin,
    ChannelNormalizationMixin,
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

    async def list_sites(self) -> list[SiteConfig]:
        """Return all configured sites."""
        async with self._session_factory() as session:
            return await self._load_sites(session)

    async def get_site(self, site_id: str) -> SiteConfig:
        """Return a site by identifier or raise when it does not exist."""
        async with self._session_factory() as session:
            sites = await self._load_sites(session, site_ids=[site_id])
            if not sites:
                raise KeyError(site_id)
            return sites[0]

    async def create_site(self, payload: SiteCreate) -> SiteConfig:
        """Create and return a site from the supplied configuration."""
        async with self._session_factory() as session:
            await self._ensure_site_name_unique(session, payload.name)
            site_id = str(uuid.uuid4())
            await self._upsert_site_payload(
                session,
                site_id,
                payload.name,
                True,
                payload.base_urls,
                payload.credentials,
                payload.protocols,
            )
            await session.commit()
        return await self.get_site(site_id)

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
            site = await session.get(SiteEntity, site_id)
            if site is None:
                raise KeyError(site_id)
            await self._ensure_site_name_unique(
                session, payload.name, exclude_site_id=site_id
            )
            await self._upsert_site_payload(
                session,
                site_id,
                payload.name,
                bool(site.enabled),
                payload.base_urls,
                payload.credentials,
                payload.protocols,
            )
            await session.commit()
        return await self.get_site(site_id)

    async def update_site_enabled(
        self, site_id: str, payload: SiteEnabledUpdate
    ) -> SiteConfig:
        """Update and return a site's master enabled state."""
        async with self._session_factory() as session:
            site = await session.get(SiteEntity, site_id)
            if site is None:
                raise KeyError(site_id)
            site.enabled = int(payload.enabled)
            await session.commit()
        return await self.get_site(site_id)
