from __future__ import annotations

from .shared import (
    AsyncSession,
    SiteConfig,
)
from ..site_loader import fetch_site_rows


class ChannelLoadersMixin:
    async def _load_sites(
        self, session: AsyncSession, site_ids: list[str] | None = None
    ) -> list[SiteConfig]:
        (
            site_rows,
            base_url_rows,
            credential_rows,
            protocol_rows,
            model_rows,
        ) = await fetch_site_rows(session, site_ids=site_ids)
        if not site_rows:
            return []

        base_urls_by_site = self._group_base_urls(base_url_rows)
        credentials_by_site, credentials_by_id = self._group_credentials(
            credential_rows
        )
        models_by_protocol_config = self._group_models(model_rows, credentials_by_id)
        protocols_by_site = self._group_protocols(
            protocol_rows, models_by_protocol_config
        )

        return [
            SiteConfig(
                id=row.id,
                name=row.name,
                base_urls=base_urls_by_site.get(row.id, []),
                credentials=credentials_by_site.get(row.id, []),
                protocols=protocols_by_site.get(row.id, []),
            )
            for row in site_rows
        ]

    async def _load_sites_by_ids(self, site_ids: list[str]) -> list[SiteConfig]:
        if not site_ids:
            return []
        async with self._session_factory() as session:
            sites = await self._load_sites(session, site_ids=site_ids)
        order = {site_id: index for index, site_id in enumerate(site_ids)}
        return sorted(sites, key=lambda item: order.get(item.id, len(order)))

    async def _site_name_keys(self, session: AsyncSession) -> set[str]:
        rows = (await session.execute(select(SiteEntity.name))).scalars().all()
        return {row.strip().lower() for row in rows if row.strip()}
