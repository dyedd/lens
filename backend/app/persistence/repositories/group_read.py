from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_prices import canonical_model_price_key
from app.models.channels import ChannelConfig
from app.models.model_groups import (
    ModelGroupCandidateItem,
    ModelGroupCandidatesRequest,
    ModelGroupCandidatesResponse,
    ModelGroupCandidateSubitem,
    ModelGroupItemInput,
    ModelGroupItemView,
    ModelGroupView,
)
from app.models.protocols import ProtocolKind
from app.persistence.entities import (
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelPriceEntity,
)
from app.persistence.group_rule_codec import (
    group_price_kwargs,
    parse_fallback_group_ids,
    parse_headers,
    parse_param_override,
)

from ...core.model_group_status import (
    ModelGroupChannelLookup,
    build_model_group_channel_lookups,
    evaluate_model_group_item,
    model_group_item_key,
)
from ...core.protocol_reachability import infer_client_protocols
from ...models.model_groups import ModelGroupItemState


@dataclass
class _CandidateAggregate:
    native_protocols: list[ProtocolKind] = field(default_factory=list)
    protocol_channels: dict[ProtocolKind, str] = field(default_factory=dict)
    site_id: str = ""
    channel_name: str = ""
    credential_name: str = ""
    credential_number: int = 0
    rate_source: Literal["none", "sub2api", "newapi"] = "none"
    rate_multiplier: float | None = None
    base_url: str = ""
    model_name: str = ""
    credential_id: str = ""
    protocol_config_id: str = ""


class GroupCandidatesMixin:
    async def _list_group_candidates(
        self, payload: ModelGroupCandidatesRequest
    ) -> ModelGroupCandidatesResponse:
        all_channels = await self._channel_store.list_channels()
        channels_by_id = build_model_group_channel_lookups(all_channels)
        selected_item_keys = {model_group_item_key(item) for item in payload.items}
        candidate_aggregates: dict[tuple[str, str, str], _CandidateAggregate] = {}

        for channel in all_channels:
            for model in channel.models:
                item = ModelGroupItemInput(
                    channel_id=channel.id,
                    credential_id=model.credential_id,
                    model_name=model.model_name,
                    enabled=True,
                )
                evaluation = evaluate_model_group_item(
                    item,
                    channels_by_id,
                )
                if evaluation.state != ModelGroupItemState.READY:
                    continue

                model_key = (
                    evaluation.protocol_config_id,
                    model.credential_id,
                    model.model_name,
                )
                credential = channels_by_id[channel.id].credentials_by_id[
                    model.credential_id
                ]
                if model_key not in candidate_aggregates:
                    candidate_aggregates[model_key] = _CandidateAggregate(
                        protocol_config_id=evaluation.protocol_config_id,
                        site_id=channel.site_id,
                        credential_id=model.credential_id,
                        credential_name=model.credential_name,
                        credential_number=credential.number,
                        rate_source=credential.rate_source,
                        rate_multiplier=credential.rate_multiplier,
                        model_name=model.model_name,
                        channel_name=channel.name,
                        base_url=str(channel.base_url),
                    )
                aggregate = candidate_aggregates[model_key]
                if channel.protocol not in aggregate.native_protocols:
                    aggregate.native_protocols.append(channel.protocol)
                aggregate.protocol_channels.setdefault(channel.protocol, channel.id)

        candidates: list[ModelGroupCandidateItem] = []
        for aggregate in candidate_aggregates.values():
            recommended_items = self._recommended_candidate_items(
                aggregate,
            )
            remaining_items = [
                item
                for item in recommended_items
                if model_group_item_key(item) not in selected_item_keys
            ]
            if not remaining_items:
                continue

            candidates.append(
                ModelGroupCandidateItem(
                    site_id=aggregate.site_id,
                    channel_name=aggregate.channel_name,
                    credential_id=aggregate.credential_id,
                    credential_name=aggregate.credential_name,
                    credential_number=aggregate.credential_number,
                    rate_source=aggregate.rate_source,
                    rate_multiplier=aggregate.rate_multiplier,
                    base_url=aggregate.base_url,
                    model_name=aggregate.model_name,
                    protocol_config_id=aggregate.protocol_config_id,
                    protocols=sorted(
                        aggregate.native_protocols, key=lambda protocol: protocol.value
                    ),
                    items=[
                        ModelGroupCandidateSubitem(
                            channel_id=item.channel_id,
                            protocol_config_id=aggregate.protocol_config_id,
                            protocol=channels_by_id[item.channel_id].channel.protocol,
                            credential_id=item.credential_id,
                            model_name=item.model_name,
                            enabled=item.enabled,
                        )
                        for item in remaining_items
                    ],
                )
            )

        candidates.sort(
            key=lambda candidate: (candidate.channel_name, candidate.model_name)
        )
        evaluated_items = [
            self._candidate_item_view(
                item,
                index,
                channels_by_id,
            )
            for index, item in enumerate(payload.items)
        ]
        return ModelGroupCandidatesResponse(
            candidates=candidates,
            evaluated_items=evaluated_items,
        )

    @staticmethod
    def _recommended_candidate_items(
        aggregate: _CandidateAggregate,
    ) -> list[ModelGroupItemInput]:
        return [
            ModelGroupItemInput(
                channel_id=channel_id,
                credential_id=aggregate.credential_id,
                model_name=aggregate.model_name,
                enabled=True,
            )
            for _, channel_id in sorted(
                aggregate.protocol_channels.items(), key=lambda item: item[0].value
            )
        ]

    @staticmethod
    def _candidate_item_view(
        item: ModelGroupItemInput,
        index: int,
        channels_by_id: Mapping[str, ModelGroupChannelLookup],
    ) -> ModelGroupItemView:
        evaluation = evaluate_model_group_item(
            item,
            channels_by_id,
        )
        channel_lookup = channels_by_id.get(item.channel_id)
        channel = channel_lookup.channel if channel_lookup is not None else None
        credential = (
            channel_lookup.credentials_by_id.get(item.credential_id)
            if channel_lookup is not None
            else None
        )
        return ModelGroupItemView(
            channel_id=item.channel_id,
            site_id=channel.site_id if channel is not None else None,
            channel_name=channel.name if channel is not None else "",
            protocol=evaluation.protocol,
            protocol_config_id=evaluation.protocol_config_id,
            credential_id=item.credential_id,
            credential_name=credential.remark if credential is not None else "",
            credential_number=credential.number if credential is not None else 0,
            rate_source=credential.rate_source if credential is not None else "none",
            rate_multiplier=(
                credential.rate_multiplier if credential is not None else None
            ),
            model_name=item.model_name,
            enabled=item.enabled,
            sort_order=index,
            state=evaluation.state,
            reasons=list(evaluation.reasons),
        )


class GroupMappingMixin:
    async def _hydrate_groups(
        self,
        session: AsyncSession,
        entities: list[ModelGroupEntity],
        channels: list[ChannelConfig],
    ) -> list[ModelGroupView]:
        if not entities:
            return []
        requested_ids = {item.id for item in entities}
        route_group_ids = {
            item.route_group_id for item in entities if item.route_group_id.strip()
        }
        missing_route_group_ids = route_group_ids - requested_ids
        if missing_route_group_ids:
            route_entities = (
                (
                    await session.execute(
                        select(ModelGroupEntity).where(
                            ModelGroupEntity.id.in_(missing_route_group_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
            entities = [*entities, *route_entities]
        items_by_group = await self._load_group_items(
            session,
            [item.id for item in entities],
            channels,
        )
        route_name_by_id = {item.id: item.name for item in entities}
        prices_by_key = await self._load_model_prices_by_keys(
            session, [canonical_model_price_key(item.name) for item in entities]
        )
        client_protocols_by_group = {
            item.id: infer_client_protocols(
                member.protocol for member in items_by_group.get(item.id, [])
            )
            for item in entities
        }
        return [
            self._to_group(
                item,
                items_by_group.get(item.id, []),
                client_protocols_by_group.get(item.route_group_id or item.id, []),
                prices_by_key.get(canonical_model_price_key(item.name)),
                route_name_by_id.get(item.route_group_id, ""),
            )
            for item in entities
            if item.id in requested_ids
        ]

    async def _load_model_prices_by_keys(
        self, session: AsyncSession, keys: list[str]
    ) -> dict[str, ModelPriceEntity]:
        canonical_keys = [key for key in dict.fromkeys(keys) if key]
        if not canonical_keys:
            return {}

        rows = (
            (
                await session.execute(
                    select(ModelPriceEntity).where(
                        ModelPriceEntity.model_key.in_(canonical_keys)
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
                    site_id=channel.site_id if channel is not None else None,
                    channel_name=channel.name if channel is not None else "",
                    protocol=evaluation.protocol,
                    protocol_config_id=evaluation.protocol_config_id,
                    credential_id=row.credential_id,
                    credential_name=credential.remark if credential is not None else "",
                    credential_number=(
                        credential.number if credential is not None else 0
                    ),
                    rate_source=(
                        credential.rate_source if credential is not None else "none"
                    ),
                    rate_multiplier=(
                        credential.rate_multiplier if credential is not None else None
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
        client_protocols: list[ProtocolKind],
        price: ModelPriceEntity | None = None,
        route_group_name: str = "",
    ) -> ModelGroupView:
        return ModelGroupView(
            id=entity.id,
            name=entity.name,
            client_protocols=client_protocols,
            strategy=entity.strategy,
            route_group_id=entity.route_group_id,
            route_group_name=route_group_name,
            sync_filter_mode=entity.sync_filter_mode,
            sync_filter_query=entity.sync_filter_query,
            param_override=parse_param_override(entity.param_override),
            headers=parse_headers(entity.headers_json),
            fallback_group_ids=parse_fallback_group_ids(entity.fallback_group_ids_json),
            **group_price_kwargs(price),
            items=items,
        )
