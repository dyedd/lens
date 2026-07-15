from __future__ import annotations

from ...core.model_group_status import (
    build_model_group_channel_lookups,
    evaluate_model_group_item,
)
from ..shared import (
    AsyncSession,
    ChannelConfig,
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelGroupItemInput,
    ModelGroupItemView,
    ModelGroupView,
    ModelPriceEntity,
    ProtocolKind,
    _parse_group_protocols,
    normalize_model_key,
    select,
)


class _GroupMappingMixin:
    async def _hydrate_groups(
        self,
        session: AsyncSession,
        entities: list[ModelGroupEntity],
        channels: list[ChannelConfig],
    ) -> list[ModelGroupView]:
        if not entities:
            return []
        protocols_by_group = {
            item.id: _parse_group_protocols(item) for item in entities
        }
        items_by_group = await self._load_group_items(
            session,
            [item.id for item in entities],
            protocols_by_group,
            channels,
        )
        route_group_ids = [
            item.route_group_id for item in entities if item.route_group_id.strip()
        ]
        route_name_by_id: dict[str, str] = {}
        if route_group_ids:
            route_rows = (
                await session.execute(
                    select(ModelGroupEntity.id, ModelGroupEntity.name).where(
                        ModelGroupEntity.id.in_(sorted(set(route_group_ids)))
                    )
                )
            ).all()
            route_name_by_id = {
                str(group_id): str(group_name) for group_id, group_name in route_rows
            }
        prices_by_key = await self._load_model_prices_by_keys(
            session, [normalize_model_key(item.name) for item in entities]
        )
        return [
            self._to_group(
                item,
                items_by_group.get(item.id, []),
                prices_by_key.get(normalize_model_key(item.name)),
                route_name_by_id.get(item.route_group_id, ""),
            )
            for item in entities
        ]

    async def _load_model_prices_by_keys(
        self, session: AsyncSession, keys: list[str]
    ) -> dict[str, ModelPriceEntity]:
        normalized_keys = [key for key in dict.fromkeys(keys) if key]
        if not normalized_keys:
            return {}

        rows = (
            (
                await session.execute(
                    select(ModelPriceEntity).where(
                        ModelPriceEntity.model_key.in_(normalized_keys)
                    )
                )
            )
            .scalars()
            .all()
        )
        return {row.model_key: row for row in rows}

    async def _load_group_items(
        self,
        session: AsyncSession,
        group_ids: list[str],
        protocols_by_group: dict[str, list[ProtocolKind]],
        channels: list[ChannelConfig],
    ) -> dict[str, list[ModelGroupItemView]]:
        if not group_ids:
            return {}

        rows = (
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

        items_by_group: dict[str, list[ModelGroupItemView]] = {
            group_id: [] for group_id in group_ids
        }
        channels_by_id = build_model_group_channel_lookups(channels)
        for row in rows:
            item = ModelGroupItemInput(
                channel_id=row.channel_id,
                credential_id=row.credential_id,
                model_name=row.model_name,
                enabled=bool(row.enabled),
            )
            evaluation = evaluate_model_group_item(
                item,
                channels_by_id,
                protocols_by_group.get(row.group_id, []),
            )
            channel_lookup = channels_by_id.get(row.channel_id)
            channel = channel_lookup.channel if channel_lookup is not None else None
            credential = (
                channel_lookup.credentials_by_id.get(row.credential_id)
                if channel_lookup is not None
                else None
            )
            items_by_group.setdefault(row.group_id, []).append(
                ModelGroupItemView(
                    channel_id=row.channel_id,
                    channel_name=channel.name if channel is not None else "",
                    protocol=evaluation.protocol,
                    protocol_config_id=evaluation.protocol_config_id,
                    credential_id=row.credential_id,
                    credential_name=credential.remark if credential is not None else "",
                    credential_number=(
                        credential.number if credential is not None else 0
                    ),
                    model_name=row.model_name,
                    enabled=bool(row.enabled),
                    sort_order=row.sort_order,
                    state=evaluation.state,
                    reasons=list(evaluation.reasons),
                )
            )
        return items_by_group

    def _replace_group_items(
        self,
        session: AsyncSession,
        group_id: str,
        items: list[ModelGroupItemInput],
    ) -> None:
        for index, item in enumerate(items):
            session.add(
                ModelGroupItemEntity(
                    group_id=group_id,
                    channel_id=item.channel_id,
                    credential_id=item.credential_id,
                    model_name=item.model_name,
                    enabled=1 if item.enabled else 0,
                    sort_order=index,
                )
            )

    @staticmethod
    def _to_group(
        entity: ModelGroupEntity,
        items: list[ModelGroupItemView],
        price: ModelPriceEntity | None = None,
        route_group_name: str = "",
    ) -> ModelGroupView:
        return ModelGroupView(
            id=entity.id,
            name=entity.name,
            protocols=_parse_group_protocols(entity),
            strategy=entity.strategy,
            route_group_id=entity.route_group_id,
            route_group_name=route_group_name,
            sync_filter_mode=entity.sync_filter_mode,
            sync_filter_query=entity.sync_filter_query,
            input_price_per_million=(
                float(price.input_price_per_million) if price is not None else 0.0
            ),
            output_price_per_million=(
                float(price.output_price_per_million) if price is not None else 0.0
            ),
            cache_read_price_per_million=(
                float(price.cache_read_price_per_million) if price is not None else 0.0
            ),
            cache_write_price_per_million=(
                float(price.cache_write_price_per_million) if price is not None else 0.0
            ),
            items=items,
        )
