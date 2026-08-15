from __future__ import annotations

import json
from collections import defaultdict

from .shared import (
    AsyncSession,
    SiteEntity,
    SiteConfig,
    select,
)
from ..site_loader import fetch_site_rows


class ChannelLoadersMixin:
    async def _load_sites(
        self, session: AsyncSession, site_ids: list[str] | None = None
    ) -> list[SiteConfig]:
        rows = await fetch_site_rows(session, site_ids=site_ids)
        if not rows.sites:
            return []

        base_urls_by_site = self._group_base_urls(rows.base_urls)
        credentials_by_site, credentials_by_id = self._group_credentials(
            rows.credentials
        )
        models_by_protocol_config = self._group_models(
            rows.discovered_models, credentials_by_id
        )
        sync_targets_by_protocol_config = self._group_sync_targets(rows.sync_targets)
        credential_ids_by_protocol_config: dict[str, list[str]] = defaultdict(list)
        for row in rows.protocol_credentials:
            credential_ids_by_protocol_config[row.protocol_config_id].append(
                row.credential_id
            )
        protocols_by_site = self._group_protocols(
            rows.protocol_configs,
            models_by_protocol_config,
            sync_targets_by_protocol_config,
            credential_ids_by_protocol_config,
        )

        return [
            SiteConfig(
                id=row.id,
                name=row.name,
                enabled=bool(row.enabled),
                tags=json.loads(row.tags_json),
                base_urls=base_urls_by_site.get(row.id, []),
                credentials=credentials_by_site.get(row.id, []),
                protocols=protocols_by_site.get(row.id, []),
            )
            for row in rows.sites
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
