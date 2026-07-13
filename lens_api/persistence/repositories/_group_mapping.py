from __future__ import annotations

from dataclasses import dataclass

from ..shared import (
    AsyncSession,
    ModelGroup,
    ModelGroupEntity,
    ModelGroupItem,
    ModelGroupItemEntity,
    ModelGroupItemInput,
    ModelPriceEntity,
    ProtocolKind,
    SiteCredentialEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    _channel_ids_by_protocol_config,
    _parse_group_protocols,
    normalize_model_key,
    select,
)


@dataclass
class _GroupItemChannelLookups:
    channel_site_names: dict[str, str]
    protocol_by_channel_id: dict[str, ProtocolKind]
    credential_names_by_channel: dict[str, dict[str, str]]
    credential_numbers_by_channel: dict[str, dict[str, int]]


class _GroupMappingMixin:
    async def _hydrate_groups(
        self, session: AsyncSession, entities: list[ModelGroupEntity]
    ) -> list[ModelGroup]:
        if not entities:
            return []
        items_by_group = await self._load_group_items(
            session, [item.id for item in entities]
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
        self, session: AsyncSession, group_ids: list[str]
    ) -> dict[str, list[ModelGroupItem]]:
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

        items_by_group: dict[str, list[ModelGroupItem]] = {
            group_id: [] for group_id in group_ids
        }
        channel_ids = list({row.channel_id for row in rows})
        lookups = await self._load_group_item_channel_lookups(session, channel_ids)
        for row in rows:
            items_by_group.setdefault(row.group_id, []).append(
                ModelGroupItem(
                    channel_id=row.channel_id,
                    channel_name=lookups.channel_site_names.get(row.channel_id, ""),
                    protocol=lookups.protocol_by_channel_id.get(row.channel_id),
                    credential_id=row.credential_id,
                    credential_name=lookups.credential_names_by_channel.get(
                        row.channel_id, {}
                    ).get(row.credential_id, ""),
                    credential_number=lookups.credential_numbers_by_channel.get(
                        row.channel_id, {}
                    ).get(row.credential_id, 0),
                    model_name=row.model_name,
                    enabled=bool(row.enabled),
                    sort_order=row.sort_order,
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

    async def _load_group_item_channel_lookups(
        self, session: AsyncSession, channel_ids: list[str]
    ) -> _GroupItemChannelLookups:
        (
            channels_by_protocol_config,
            protocol_by_channel_id,
        ) = _channel_ids_by_protocol_config(channel_ids)
        if not channels_by_protocol_config:
            return _GroupItemChannelLookups({}, {}, {}, {})

        protocol_config_ids = list(channels_by_protocol_config.keys())
        site_rows = (
            await session.execute(
                select(
                    SiteProtocolConfigEntity.id,
                    SiteEntity.name,
                )
                .join(SiteEntity, SiteEntity.id == SiteProtocolConfigEntity.site_id)
                .where(SiteProtocolConfigEntity.id.in_(protocol_config_ids))
            )
        ).all()
        site_names_by_protocol_config: dict[str, str] = {
            str(protocol_config_id): str(site_name)
            for protocol_config_id, site_name in site_rows
        }
        credential_rows = await session.execute(
            select(
                SiteProtocolConfigEntity.id,
                SiteCredentialEntity.id,
                SiteCredentialEntity.name,
                SiteCredentialEntity.sort_order,
            )
            .join(
                SiteCredentialEntity,
                SiteCredentialEntity.site_id == SiteProtocolConfigEntity.site_id,
            )
            .where(SiteProtocolConfigEntity.id.in_(protocol_config_ids))
            .order_by(
                SiteProtocolConfigEntity.id.asc(),
                SiteCredentialEntity.sort_order.asc(),
                SiteCredentialEntity.id.asc(),
            )
        )
        credential_names_by_protocol_config: dict[str, dict[str, str]] = {}
        credential_numbers_by_protocol_config: dict[str, dict[str, int]] = {}
        credential_counts_by_protocol_config: dict[str, int] = {}
        for (
            protocol_config_id,
            credential_id,
            credential_name,
            _sort_order,
        ) in credential_rows.all():
            protocol_config_id = str(protocol_config_id)
            credential_id = str(credential_id)
            credential_names_by_protocol_config.setdefault(protocol_config_id, {})[
                credential_id
            ] = str(credential_name)
            credential_counts_by_protocol_config[protocol_config_id] = (
                credential_counts_by_protocol_config.get(protocol_config_id, 0) + 1
            )
            credential_numbers_by_protocol_config.setdefault(protocol_config_id, {})[
                credential_id
            ] = credential_counts_by_protocol_config[protocol_config_id]

        channel_site_names: dict[str, str] = {}
        credential_names_by_channel: dict[str, dict[str, str]] = {}
        credential_numbers_by_channel: dict[str, dict[str, int]] = {}
        for (
            protocol_config_id,
            channel_ids_for_config,
        ) in channels_by_protocol_config.items():
            site_name = site_names_by_protocol_config.get(protocol_config_id, "")
            credential_names = credential_names_by_protocol_config.get(
                protocol_config_id, {}
            )
            credential_numbers = credential_numbers_by_protocol_config.get(
                protocol_config_id, {}
            )
            for channel_id in channel_ids_for_config:
                channel_site_names[channel_id] = site_name
                credential_names_by_channel[channel_id] = credential_names
                credential_numbers_by_channel[channel_id] = credential_numbers
        return _GroupItemChannelLookups(
            channel_site_names=channel_site_names,
            protocol_by_channel_id=protocol_by_channel_id,
            credential_names_by_channel=credential_names_by_channel,
            credential_numbers_by_channel=credential_numbers_by_channel,
        )

    @staticmethod
    def _to_group(
        entity: ModelGroupEntity,
        items: list[ModelGroupItem],
        price: ModelPriceEntity | None = None,
        route_group_name: str = "",
    ) -> ModelGroup:
        return ModelGroup(
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
