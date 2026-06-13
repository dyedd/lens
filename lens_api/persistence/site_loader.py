from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .entities import (
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)


async def fetch_site_rows(
    session: AsyncSession, site_ids: list[str] | None = None
) -> tuple[
    list[SiteEntity],
    list[SiteBaseUrlEntity],
    list[SiteCredentialEntity],
    list[SiteProtocolConfigEntity],
    list[SiteDiscoveredModelEntity],
]:
    site_query = select(SiteEntity).order_by(SiteEntity.name.asc())
    if site_ids is not None:
        site_query = site_query.where(SiteEntity.id.in_(site_ids))
    site_rows = (await session.execute(site_query)).scalars().all()
    if not site_rows:
        return [], [], [], [], []

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

    return site_rows, base_url_rows, credential_rows, protocol_rows, model_rows
