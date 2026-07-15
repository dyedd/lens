from __future__ import annotations

from .shared import (
    AsyncSession,
    ChannelConfig,
    ModelGroupItemEntity,
    ProtocolKind,
    SiteBaseUrlEntity,
    SiteBatchImportError,
    SiteBatchImportRequest,
    SiteBatchImportResult,
    SiteBatchImportSkipped,
    SiteConfig,
    SiteCreate,
    SiteCredential,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
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
from .site_batch_import import ChannelSiteBatchImportMixin
from .site_import_normalization import ChannelSiteImportNormalizationMixin
from .site_operations import ChannelSiteOperationsMixin
from .upserts import ChannelUpsertsMixin
from ..shared import _parse_supported_protocols_json


class ChannelStore(
    ChannelLoadersMixin,
    ChannelSiteImportNormalizationMixin,
    ChannelNormalizationMixin,
    ChannelUpsertsMixin,
    ChannelSiteBatchImportMixin,
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
                payload.base_urls,
                payload.credentials,
                payload.protocols,
            )
            await session.commit()
        return await self.get_site(site_id)

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
                payload.base_urls,
                payload.credentials,
                payload.protocols,
            )
            await session.commit()
        return await self.get_site(site_id)
