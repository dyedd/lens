from __future__ import annotations

from .shared import (
    AsyncSession,
    SiteBaseUrlEntity,
    SiteConfig,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    select,
)


class ChannelLoadersMixin:
    async def _load_sites(
        self, session: AsyncSession, site_ids: list[str] | None = None
    ) -> list[SiteConfig]:
        site_query = select(SiteEntity).order_by(SiteEntity.name.asc())
        if site_ids is not None:
            site_query = site_query.where(SiteEntity.id.in_(site_ids))
        site_rows = (await session.execute(site_query)).scalars().all()
        if not site_rows:
            return []

        ids = [item.id for item in site_rows]
        base_url_rows = (
            (
                await session.execute(
                    select(SiteBaseUrlEntity)
                    .where(SiteBaseUrlEntity.site_id.in_(ids))
                    .order_by(
                        SiteBaseUrlEntity.site_id.asc(),
                        SiteBaseUrlEntity.sort_order.asc(),
                        SiteBaseUrlEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        credential_rows = (
            (
                await session.execute(
                    select(SiteCredentialEntity)
                    .where(SiteCredentialEntity.site_id.in_(ids))
                    .order_by(
                        SiteCredentialEntity.site_id.asc(),
                        SiteCredentialEntity.sort_order.asc(),
                        SiteCredentialEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        protocol_rows = (
            (
                await session.execute(
                    select(SiteProtocolConfigEntity)
                    .where(SiteProtocolConfigEntity.site_id.in_(ids))
                    .order_by(
                        SiteProtocolConfigEntity.site_id.asc(),
                        SiteProtocolConfigEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        protocol_config_ids = [item.id for item in protocol_rows]
        model_rows = []
        if protocol_config_ids:
            model_rows = (
                (
                    await session.execute(
                        select(SiteDiscoveredModelEntity)
                        .where(
                            SiteDiscoveredModelEntity.protocol_config_id.in_(
                                protocol_config_ids
                            )
                        )
                        .order_by(
                            SiteDiscoveredModelEntity.protocol_config_id.asc(),
                            SiteDiscoveredModelEntity.sort_order.asc(),
                            SiteDiscoveredModelEntity.id.asc(),
                        )
                    )
                )
                .scalars()
                .all()
            )

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
