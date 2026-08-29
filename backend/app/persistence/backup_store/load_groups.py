from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_prices import canonical_model_price_key
from app.core.runtime_channel_ids import extract_protocol_config_id
from app.models.model_groups import ModelGroup
from app.models.upstream_rules import HeaderRule, ParamOverrideRule
from app.persistence.entities import (
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelPriceEntity,
    SiteCredentialEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)


async def _load_groups(self, session: AsyncSession) -> list[ModelGroup]:
    group_rows = (
        (
            await session.execute(
                select(ModelGroupEntity).order_by(ModelGroupEntity.name)
            )
        )
        .scalars()
        .all()
    )
    if not group_rows:
        return []

    group_ids = [item.id for item in group_rows]
    item_rows = (
        (
            await session.execute(
                select(ModelGroupItemEntity)
                .where(ModelGroupItemEntity.group_id.in_(group_ids))
                .order_by(
                    ModelGroupItemEntity.group_id.asc(),
                    ModelGroupItemEntity.sort_order.asc(),
                    ModelGroupItemEntity.id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )

    site_names = {
        row.id: row.name
        for row in (await session.execute(select(SiteEntity.id, SiteEntity.name))).all()
    }
    credential_names = {
        row.id: row.name
        for row in (
            await session.execute(
                select(SiteCredentialEntity.id, SiteCredentialEntity.name)
            )
        ).all()
    }
    route_group_names = {
        row.id: row.name
        for row in (
            await session.execute(select(ModelGroupEntity.id, ModelGroupEntity.name))
        ).all()
    }
    channel_site_ids = {
        row.id: row.site_id
        for row in (
            await session.execute(
                select(SiteProtocolConfigEntity.id, SiteProtocolConfigEntity.site_id)
            )
        ).all()
    }
    protocol_config_ids = set(channel_site_ids)

    items_by_group: dict[str, list[dict[str, object]]] = {}
    for row in item_rows:
        protocol_config_id = extract_protocol_config_id(
            row.channel_id, protocol_config_ids
        )
        items_by_group.setdefault(row.group_id, []).append(
            {
                "channel_id": row.channel_id,
                "channel_name": site_names.get(
                    channel_site_ids.get(protocol_config_id, ""), ""
                ),
                "credential_id": row.credential_id,
                "credential_name": credential_names.get(row.credential_id, ""),
                "model_name": row.model_name,
                "enabled": bool(row.enabled),
                "sort_order": row.sort_order,
            }
        )

    price_rows = (await session.execute(select(ModelPriceEntity))).scalars().all()
    prices_by_key = {row.model_key: row for row in price_rows}

    groups: list[ModelGroup] = []
    for row in group_rows:
        price_key = canonical_model_price_key(row.name)
        price = prices_by_key.get(price_key)
        groups.append(
            ModelGroup.model_validate(
                {
                    "id": row.id,
                    "name": row.name,
                    "strategy": row.strategy,
                    "route_group_id": row.route_group_id,
                    "route_group_name": route_group_names.get(row.route_group_id, ""),
                    "sync_filter_mode": row.sync_filter_mode,
                    "sync_filter_query": row.sync_filter_query,
                    "param_override": [
                        ParamOverrideRule.model_validate(item)
                        for item in json.loads(row.param_override)
                    ],
                    "headers": [
                        HeaderRule.model_validate(item)
                        for item in json.loads(row.headers_json)
                    ],
                    "input_price_per_million": (
                        price.input_price_per_million if price is not None else 0.0
                    ),
                    "output_price_per_million": (
                        price.output_price_per_million if price is not None else 0.0
                    ),
                    "cache_read_price_per_million": (
                        price.cache_read_price_per_million if price is not None else 0.0
                    ),
                    "cache_write_price_per_million": (
                        price.cache_write_price_per_million
                        if price is not None
                        else 0.0
                    ),
                    "image_price_per_image": (
                        price.image_price_per_image if price is not None else 0.0
                    ),
                    "pricing_mode": (
                        price.pricing_mode if price is not None else "tokens"
                    ),
                    "items": items_by_group.get(row.id, []),
                }
            )
        )
    return groups
