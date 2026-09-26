from __future__ import annotations

import uuid

from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ResourceConflictError, ResourceNotFoundError
from app.models.channels import ChannelConfig
from app.models.model_groups import (
    ModelGroupCandidatesRequest,
    ModelGroupCandidatesResponse,
    ModelGroupCreate,
    ModelGroupItemInput,
    ModelGroupUpdate,
    ModelGroupView,
    canonicalize_match_models,
    canonicalize_match_regex,
)
from app.persistence.entities import (
    ModelGroupEntity,
    ModelGroupItemEntity,
)
from app.persistence.group_rule_codec import (
    dump_fallback_group_ids,
    dump_match_models,
    dump_rules,
    parse_fallback_group_ids,
    parse_match_models,
)

from ..channel_store import ChannelStore
from .group_placement import GroupPlacementMixin
from .group_read import GroupCandidatesMixin, GroupMappingMixin
from .group_write import GroupValidationMixin


class ModelGroupRepository(
    GroupPlacementMixin,
    GroupCandidatesMixin,
    GroupValidationMixin,
    GroupMappingMixin,
):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._channel_store = ChannelStore(session_factory)

    async def list_groups(
        self, *, channels: list[ChannelConfig] | None = None
    ) -> list[ModelGroupView]:
        """Return all model groups with hydrated members and pricing."""
        effective_channels = (
            channels
            if channels is not None
            else await self._channel_store.list_channels()
        )
        async with self._session_factory() as session:
            entities = (
                (
                    await session.execute(
                        select(ModelGroupEntity).order_by(ModelGroupEntity.name)
                    )
                )
                .scalars()
                .all()
            )
            return await self._hydrate_groups(session, entities, effective_channels)

    async def get_group(
        self, group_id: str, *, channels: list[ChannelConfig] | None = None
    ) -> ModelGroupView:
        """Return a model group by identifier or raise when it does not exist."""
        effective_channels = (
            channels
            if channels is not None
            else await self._channel_store.list_channels()
        )
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise ResourceNotFoundError(group_id)
            hydrated = await self._hydrate_groups(session, [entity], effective_channels)
            return hydrated[0]

    async def find_group_by_name(
        self,
        protocol: str,
        name: str | None,
        *,
        channels: list[ChannelConfig] | None = None,
    ) -> ModelGroupView | None:
        """Return the model group named exactly as requested for one protocol."""
        trimmed_name = (name or "").strip()
        if not trimmed_name:
            return None

        effective_channels = (
            channels
            if channels is not None
            else await self._channel_store.list_channels()
        )
        async with self._session_factory() as session:
            result = await session.execute(
                select(ModelGroupEntity)
                .where(ModelGroupEntity.name == trimmed_name)
                .limit(1)
            )
            entity = result.scalar_one_or_none()
            if entity is None:
                return None
            hydrated = await self._hydrate_groups(session, [entity], effective_channels)
            group = hydrated[0]
        return (
            group
            if protocol in {item.value for item in group.client_protocols}
            else None
        )

    async def list_group_candidates(
        self, payload: ModelGroupCandidatesRequest
    ) -> ModelGroupCandidatesResponse:
        """Return enabled model candidates and evaluate selected members."""
        return await self._list_group_candidates(payload)

    async def create_group(self, payload: ModelGroupCreate) -> ModelGroupView:
        """Create and return a validated model group."""
        channels = await self._channel_store.list_channels()
        async with self._session_factory() as session:
            route_group = await self._validate_group_payload(
                session,
                payload.name,
                payload.route_group_id,
                payload.items,
                fallback_group_ids=payload.fallback_group_ids,
                channels=channels,
            )
            entity = ModelGroupEntity(
                id=str(uuid.uuid4()),
                name=payload.name.strip(),
                strategy=payload.strategy.value,
                route_group_id=route_group.id if route_group is not None else "",
                match_models_json=dump_match_models(payload.match_models),
                match_regex=payload.match_regex,
                param_override=dump_rules(payload.param_override),
                headers_json=dump_rules(payload.headers),
                fallback_group_ids_json=dump_fallback_group_ids(
                    payload.fallback_group_ids
                ),
            )
            session.add(entity)
            await session.flush()
            self._replace_group_items(session, entity.id, payload.items)
            await session.commit()
            await session.refresh(entity)
            hydrated = await self._hydrate_groups(session, [entity], channels)
            return hydrated[0]

    async def update_group(
        self, group_id: str, payload: ModelGroupUpdate
    ) -> ModelGroupView:
        """Update and return an existing model group."""
        channels = await self._channel_store.list_channels()
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise ResourceNotFoundError(group_id)

            next_name = payload.name if payload.name is not None else entity.name
            next_route_group_id = (
                payload.route_group_id
                if payload.route_group_id is not None
                else entity.route_group_id
            )
            inbound_route_group_result = await session.execute(
                select(ModelGroupEntity.id)
                .where(ModelGroupEntity.route_group_id == group_id)
                .where(ModelGroupEntity.id != group_id)
                .limit(1)
            )
            has_inbound_route_group = (
                inbound_route_group_result.scalar_one_or_none() is not None
            )
            if next_route_group_id and has_inbound_route_group:
                raise ValueError(
                    "Execution groups referenced by route groups cannot become route groups"
                )
            validates_items = payload.items is not None
            current_item_views = []
            if validates_items:
                current_items = await self._load_group_items(
                    session,
                    [group_id],
                    channels,
                )
                current_item_views = current_items.get(group_id, [])
            next_items = payload.items
            if next_items is None and validates_items:
                next_items = [
                    ModelGroupItemInput(
                        channel_id=item.channel_id,
                        credential_id=item.credential_id,
                        model_name=item.model_name,
                        enabled=item.enabled,
                    )
                    for item in current_item_views
                ]
            next_fallback_group_ids = (
                payload.fallback_group_ids
                if payload.fallback_group_ids is not None
                else parse_fallback_group_ids(entity.fallback_group_ids_json)
            )
            route_group = await self._validate_group_payload(
                session,
                next_name,
                next_route_group_id,
                next_items if validates_items else None,
                exclude_group_id=group_id,
                fallback_group_ids=next_fallback_group_ids,
                channels=channels,
                existing_items=current_item_views,
            )

            changes = payload.model_dump(exclude_unset=True)
            for key, value in changes.items():
                if key == "strategy" and value is not None:
                    entity.strategy = value.value
                elif key == "match_models":
                    entity.match_models_json = dump_match_models(value or [])
                elif key == "match_regex":
                    entity.match_regex = value or ""
                elif key == "items":
                    continue
                elif key == "fallback_group_ids":
                    entity.fallback_group_ids_json = dump_fallback_group_ids(value)
                elif key == "headers":
                    entity.headers_json = dump_rules(value)
                elif key == "param_override":
                    entity.param_override = dump_rules(value)
                elif key == "route_group_id":
                    entity.route_group_id = (
                        route_group.id if route_group is not None else ""
                    )
                else:
                    setattr(entity, key, value)

            if entity.route_group_id:
                entity.match_models_json = dump_match_models([])
                entity.match_regex = ""

            if payload.items is not None:
                await session.execute(
                    delete(ModelGroupItemEntity).where(
                        ModelGroupItemEntity.group_id == group_id
                    )
                )
                self._replace_group_items(session, group_id, next_items or [])

            await session.commit()
            await session.refresh(entity)
            hydrated = await self._hydrate_groups(session, [entity], channels)
            return hydrated[0]

    async def delete_group(self, group_id: str) -> None:
        """Delete an unreferenced model group and its members."""
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise ResourceNotFoundError(group_id)
            inbound_route_group = await session.execute(
                select(ModelGroupEntity.id)
                .where(ModelGroupEntity.route_group_id == group_id)
                .where(ModelGroupEntity.id != group_id)
                .limit(1)
            )
            if inbound_route_group.scalar_one_or_none() is not None:
                raise ValueError("Model group is still referenced by route groups")
            await session.execute(
                delete(ModelGroupItemEntity).where(
                    ModelGroupItemEntity.group_id == group_id
                )
            )
            await session.delete(entity)
            await session.commit()

    async def merge_group(self, group_id: str, target_group_id: str) -> ModelGroupView:
        """Fold a group's name, rules, and members into another execution group."""
        channels = await self._channel_store.list_channels()
        async with self._session_factory() as session:
            source = await session.get(ModelGroupEntity, group_id)
            if source is None:
                raise ResourceNotFoundError(group_id)
            target = await session.get(ModelGroupEntity, target_group_id)
            if target is None:
                raise ResourceNotFoundError(target_group_id)
            if source.id == target.id:
                raise ResourceConflictError("Model group cannot merge into itself")
            if target.route_group_id.strip():
                raise ResourceConflictError("Merge target must be an execution group")

            target.match_models_json = dump_match_models(
                canonicalize_match_models(
                    [
                        *parse_match_models(target.match_models_json),
                        source.name,
                        *parse_match_models(source.match_models_json),
                    ]
                )
                or []
            )
            patterns = [
                item for item in (target.match_regex, source.match_regex) if item
            ]
            target.match_regex = (
                canonicalize_match_regex(
                    "|".join(f"(?:{item})" for item in patterns)
                    if len(patterns) > 1
                    else "".join(patterns)
                )
                or ""
            )

            item_rows = (
                (
                    await session.execute(
                        select(ModelGroupItemEntity)
                        .where(
                            ModelGroupItemEntity.group_id.in_([target.id, source.id])
                        )
                        .order_by(
                            ModelGroupItemEntity.sort_order.asc(),
                            ModelGroupItemEntity.id.asc(),
                        )
                    )
                )
                .scalars()
                .all()
            )
            target_rows = [row for row in item_rows if row.group_id == target.id]
            member_keys = {
                (row.channel_id, row.credential_id, row.model_name)
                for row in target_rows
            }
            next_sort_order = len(target_rows)
            for row in item_rows:
                if row.group_id != source.id:
                    continue
                row_key = (row.channel_id, row.credential_id, row.model_name)
                if row_key in member_keys:
                    await session.delete(row)
                    continue
                member_keys.add(row_key)
                row.group_id = target.id
                row.sort_order = next_sort_order
                next_sort_order += 1

            for entity in (await session.execute(select(ModelGroupEntity))).scalars():
                if entity.id == source.id:
                    continue
                if entity.route_group_id == source.id:
                    entity.route_group_id = target.id
                fallback_group_ids = parse_fallback_group_ids(
                    entity.fallback_group_ids_json
                )
                if source.id in fallback_group_ids:
                    entity.fallback_group_ids_json = dump_fallback_group_ids(
                        [
                            fallback_id
                            for fallback_id in dict.fromkeys(
                                target.id if item == source.id else item
                                for item in fallback_group_ids
                            )
                            if fallback_id != entity.id
                        ]
                    )

            await session.delete(source)
            await session.commit()
            hydrated = await self._hydrate_groups(session, [target], channels)
            return hydrated[0]

    async def list_group_names(self, *, include_routed: bool = False) -> list[str]:
        """Return model group names, optionally including routed groups."""
        from sqlalchemy import select

        from app.persistence.entities import ModelGroupEntity

        async with self._session_factory() as session:
            query = select(ModelGroupEntity.name).order_by(ModelGroupEntity.name.asc())
            if not include_routed:
                query = query.where(ModelGroupEntity.route_group_id == "")
            rows = await session.execute(query)
            return [str(item) for item in rows.scalars().all() if str(item).strip()]
