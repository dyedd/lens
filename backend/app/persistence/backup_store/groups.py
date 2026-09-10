from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_group_status import model_group_item_key
from app.core.model_prices import canonical_model_price_key
from app.core.runtime_channel_ids import (
    protocol_config_id_from_runtime_channel_id,
    split_runtime_channel_id,
)
from app.models.model_groups import ModelGroup
from app.persistence.entities import (
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelPriceEntity,
    SiteCredentialEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)
from app.persistence.group_rule_codec import (
    dump_fallback_group_ids,
    dump_rules,
    group_price_kwargs,
    parse_fallback_group_ids,
    parse_headers,
    parse_param_override,
)


async def load_groups(self, session: AsyncSession) -> list[ModelGroup]:
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
    items_by_group: dict[str, list[dict[str, object]]] = {}
    for row in item_rows:
        protocol_config_id = protocol_config_id_from_runtime_channel_id(row.channel_id)
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
                    "param_override": parse_param_override(row.param_override),
                    "headers": parse_headers(row.headers_json),
                    "fallback_group_ids": parse_fallback_group_ids(
                        row.fallback_group_ids_json
                    ),
                    **group_price_kwargs(price),
                    "items": items_by_group.get(row.id, []),
                }
            )
        )
    return groups


async def replace_groups(
    self,
    session: AsyncSession,
    groups: list[ModelGroup],
    *,
    available_protocol_config_ids: set[str],
    model_keys: set[tuple[str, str, str]],
) -> None:
    await session.execute(delete(ModelGroupItemEntity))
    await session.execute(delete(ModelGroupEntity))

    group_ids = {group.id for group in groups}
    seen_group_names: set[str] = set()
    seen_group_ids: set[str] = set()

    groups_by_id = {group.id: group for group in groups}
    for group in groups:
        is_synced_group = bool(group.sync_filter_mode.value)
        if group.id in seen_group_ids:
            raise ValueError(f"Duplicate group id in backup: {group.id}")
        seen_group_ids.add(group.id)

        if group.name in seen_group_names:
            raise ValueError(f"Duplicate model group name in backup: {group.name}")
        seen_group_names.add(group.name)

        if group.route_group_id and group.route_group_id not in group_ids:
            raise ValueError(
                f"Referenced route group not found: {group.route_group_id}"
            )
        if group.route_group_id:
            route_group = groups_by_id[group.route_group_id]
            if route_group.route_group_id:
                raise ValueError(
                    f"Route target must be an execution group: {route_group.name}"
                )
        for fallback_group_id in group.fallback_group_ids:
            if fallback_group_id == group.id:
                raise ValueError(
                    f"Model group cannot fall back to itself: {group.name}"
                )
            fallback_group = groups_by_id.get(fallback_group_id)
            if fallback_group is None:
                raise ValueError(f"Fallback model group not found: {fallback_group_id}")
            if fallback_group.route_group_id:
                raise ValueError("Fallback model groups must be execution groups")

        resolved_item_keys: set[tuple[str, str, str]] = set()

        for item in group.items:
            parsed_channel_id = split_runtime_channel_id(item.channel_id)
            if parsed_channel_id is None or (
                is_synced_group
                and parsed_channel_id[0] not in available_protocol_config_ids
            ):
                raise ValueError(
                    f"Model group channel not found in backup sites: {item.channel_id}"
                )
            target = model_group_item_key(item)
            if target in resolved_item_keys:
                raise ValueError(
                    "Duplicate model group member in backup "
                    f"{group.name}: channel={item.channel_id} "
                    f"credential={item.credential_id} model={item.model_name}"
                )
            resolved_item_keys.add(target)
            if is_synced_group and target not in model_keys:
                raise ValueError(
                    f"Model group model not found in backup channel {item.channel_id} credential={item.credential_id}: {item.model_name}"
                )

        session.add(
            ModelGroupEntity(
                id=group.id,
                name=group.name,
                strategy=group.strategy.value,
                route_group_id=group.route_group_id,
                sync_filter_mode=group.sync_filter_mode.value,
                sync_filter_query=group.sync_filter_query,
                param_override=dump_rules(group.param_override),
                headers_json=dump_rules(group.headers),
                fallback_group_ids_json=dump_fallback_group_ids(
                    group.fallback_group_ids
                ),
            )
        )

        for index, item in enumerate(group.items):
            session.add(
                ModelGroupItemEntity(
                    group_id=group.id,
                    channel_id=item.channel_id,
                    credential_id=item.credential_id,
                    model_name=item.model_name,
                    enabled=1 if item.enabled else 0,
                    sort_order=item.sort_order if item.sort_order >= 0 else index,
                )
            )
