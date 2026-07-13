from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .entities import (
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)


@dataclass(frozen=True, slots=True)
class SiteRows:
    sites: list[SiteEntity]
    base_urls: list[SiteBaseUrlEntity]
    credentials: list[SiteCredentialEntity]
    protocol_configs: list[SiteProtocolConfigEntity]
    discovered_models: list[SiteDiscoveredModelEntity]


async def fetch_site_rows(
    session: AsyncSession, site_ids: list[str] | None = None
) -> SiteRows:
    """Load sites and their related configuration rows in stable order."""
    site_query = select(SiteEntity).order_by(SiteEntity.name.asc())
    if site_ids is not None:
        site_query = site_query.where(SiteEntity.id.in_(site_ids))
    site_rows = (await session.execute(site_query)).scalars().all()
    if not site_rows:
        return SiteRows([], [], [], [], [])

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
    model_rows: list[SiteDiscoveredModelEntity] = []
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

    return SiteRows(
        sites=site_rows,
        base_urls=base_url_rows,
        credentials=credential_rows,
        protocol_configs=protocol_rows,
        discovered_models=model_rows,
    )
