from __future__ import annotations

import uuid

from sqlalchemy import (
    delete,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ResourceConflictError, ResourceNotFoundError
from app.core.model_catalog import ModelCatalog
from app.core.model_group_matching import (
    compile_model_group_pattern,
    matches_model_group,
)
from app.core.model_group_status import model_group_item_key
from app.models.channels import ChannelConfig
from app.models.model_groups import (
    ModelGroupCandidatesRequest,
    ModelGroupCandidatesResponse,
    ModelGroupCreate,
    ModelGroupItemInput,
    ModelGroupItemState,
    ModelGroupItemView,
    ModelGroupMemberSource,
    ModelGroupUpdate,
    ModelGroupView,
)
from app.persistence.entities import (
    ModelGroupEntity,
    ModelGroupItemEntity,
)
from app.persistence.group_rule_codec import (
    dump_fallback_group_ids,
    dump_rules,
    parse_fallback_group_ids,
)
from app.persistence.regex_rule_references import (
    dump_rule_ids,
)

from ..channel_store import ChannelStore
from .group_placement import GroupPlacementMixin
from .group_read import GroupCandidatesMixin, GroupMappingMixin
from .group_reconcile import GroupReconcileMixin
from .group_write import GroupValidationMixin


def _view_to_input(item: ModelGroupItemView) -> ModelGroupItemInput:
    return ModelGroupItemInput(
        channel_id=item.channel_id,
        credential_id=item.credential_id,
        model_name=item.model_name,
        enabled=item.enabled,
        source=item.source,
    )


class ModelGroupRepository(
    GroupReconcileMixin,
    GroupPlacementMixin,
    GroupCandidatesMixin,
    GroupValidationMixin,
    GroupMappingMixin,
):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        model_catalog: ModelCatalog | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._channel_store = ChannelStore(session_factory, model_catalog=model_catalog)

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
                route_group_id=payload.route_group_id,
                items=payload.items,
                fallback_group_ids=payload.fallback_group_ids,
                channels=channels,
                excluded_items=payload.excluded_items,
            )
            entity = ModelGroupEntity(
                id=str(uuid.uuid4()),
                name=payload.name.strip(),
                strategy=payload.strategy.value,
                route_group_id=route_group.id if route_group is not None else "",
                match_regex=payload.match_regex,
                match_regex_operator=payload.match_regex_operator,
                match_rule_ids_json=dump_rule_ids([]),
                param_override=dump_rules(payload.param_override),
                headers_json=dump_rules(payload.headers),
                fallback_group_ids_json=dump_fallback_group_ids(
                    payload.fallback_group_ids
                ),
                context_window=payload.context_window,
            )
            session.add(entity)
            await session.flush()
            self._replace_group_items(
                session, entity.id, payload.items, payload.excluded_items
            )
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

            next_name = (
                payload.name.strip() if payload.name is not None else entity.name
            )
            is_renamed = next_name != entity.name
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
            replaces_items = (
                payload.items is not None or payload.excluded_items is not None
            )
            current_item_views = []
            current_excluded_views = []
            if replaces_items:
                current_items = await self._load_group_items(
                    session,
                    [group_id],
                    channels,
                )
                current_item_views = current_items.members.get(group_id, [])
                current_excluded_views = current_items.excluded.get(group_id, [])
            next_items = (
                payload.items
                if payload.items is not None
                else [_view_to_input(item) for item in current_item_views]
            )
            next_excluded_items = (
                payload.excluded_items
                if payload.excluded_items is not None
                else [_view_to_input(item) for item in current_excluded_views]
            )
            next_fallback_group_ids = (
                payload.fallback_group_ids
                if payload.fallback_group_ids is not None
                else parse_fallback_group_ids(entity.fallback_group_ids_json)
            )
            route_group = await self._validate_group_payload(
                session,
                next_name,
                route_group_id=next_route_group_id,
                items=next_items if replaces_items else None,
                exclude_group_id=group_id,
                fallback_group_ids=next_fallback_group_ids,
                channels=channels,
                existing_items=current_item_views,
                excluded_items=next_excluded_items,
            )
            changes = payload.model_dump(exclude_unset=True)
            for key, value in changes.items():
                if key == "strategy" and value is not None:
                    entity.strategy = value.value
                elif key == "match_regex":
                    if value is not None:
                        entity.match_regex = value
                        entity.match_rule_ids_json = dump_rule_ids([])
                elif key == "match_regex_operator":
                    if value is not None:
                        entity.match_regex_operator = value
                elif key in {"items", "excluded_items"}:
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
                elif key == "name" and value is not None:
                    entity.name = value.strip()
                else:
                    setattr(entity, key, value)

            if entity.route_group_id:
                entity.match_regex = ""
                entity.match_regex_operator = "or"
                entity.match_rule_ids_json = dump_rule_ids([])

            if replaces_items:
                # Only a caller that does not send exclusions gets removed
                # automatic members excluded for it. The editor sends its own
                # list, so a member a sync added while it was open is not
                # mistaken for a removal; reconcile puts that member back.
                if not entity.route_group_id and payload.excluded_items is None:
                    next_excluded_items = [
                        *next_excluded_items,
                        *await self._exclude_removed_auto_members(
                            session,
                            entity,
                            current_item_views,
                            next_items,
                            next_excluded_items,
                        ),
                    ]
                await session.execute(
                    delete(ModelGroupItemEntity).where(
                        ModelGroupItemEntity.group_id == group_id
                    )
                )
                self._replace_group_items(
                    session,
                    group_id,
                    next_items,
                    next_excluded_items,
                )
            elif is_renamed:
                # Renaming a group keeps the members it already has, even the
                # ones a reconcile joined by the old name.
                await session.execute(
                    update(ModelGroupItemEntity)
                    .where(ModelGroupItemEntity.group_id == group_id)
                    .values(source=ModelGroupMemberSource.MANUAL.value)
                )

            await session.commit()
            await session.refresh(entity)
            hydrated = await self._hydrate_groups(session, [entity], channels)
            return hydrated[0]

    @staticmethod
    async def _exclude_removed_auto_members(
        session: AsyncSession,
        entity: ModelGroupEntity,
        previous_items: list[ModelGroupItemView],
        next_items: list[ModelGroupItemInput],
        next_excluded_items: list[ModelGroupItemInput],
    ) -> list[ModelGroupItemInput]:
        """Turn removed members that reconcile would re-add into exclusions."""
        kept_keys = {
            model_group_item_key(item) for item in (*next_items, *next_excluded_items)
        }
        direct_pattern = compile_model_group_pattern(entity.match_regex)
        patterns = (direct_pattern,) if direct_pattern is not None else ()
        operator = (
            entity.match_regex_operator
            if entity.match_regex_operator in {"and", "or"}
            else "or"
        )

        def rejoins(item: ModelGroupItemView) -> bool:
            return matches_model_group(entity.name, item.model_name, patterns, operator)

        # A member whose target is gone cannot rejoin, so it needs no exclusion.
        return [
            ModelGroupItemInput(
                channel_id=item.channel_id,
                credential_id=item.credential_id,
                model_name=item.model_name,
                enabled=item.enabled,
                source=item.source,
            )
            for item in previous_items
            if model_group_item_key(item) not in kept_keys
            and item.state != ModelGroupItemState.INVALID
            and rejoins(item)
        ]

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
            fallback_rows = (
                await session.execute(
                    select(
                        ModelGroupEntity.id,
                        ModelGroupEntity.fallback_group_ids_json,
                    ).where(ModelGroupEntity.id != group_id)
                )
            ).all()
            if any(
                group_id in parse_fallback_group_ids(fallback_ids_json)
                for _, fallback_ids_json in fallback_rows
            ):
                raise ResourceConflictError(
                    "Model group is still referenced as a fallback"
                )
            await session.execute(
                delete(ModelGroupItemEntity).where(
                    ModelGroupItemEntity.group_id == group_id
                )
            )
            await session.delete(entity)
            await session.commit()

    async def merge_group(self, group_id: str, target_group_id: str) -> ModelGroupView:
        """Fold a group's members and references into another execution group."""
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

            if target.context_window is None:
                target.context_window = source.context_window
            target_pattern = target.match_regex.strip()
            source_pattern = source.match_regex.strip()
            if target_pattern and source_pattern:
                target.match_regex = f"(?:{target_pattern})|(?:{source_pattern})"
                target.match_regex_operator = "or"
                target.match_rule_ids_json = dump_rule_ids([])
            elif source_pattern:
                target.match_regex = source_pattern
                target.match_regex_operator = (
                    source.match_regex_operator
                    if source.match_regex_operator in {"and", "or"}
                    else "or"
                )
                target.match_rule_ids_json = dump_rule_ids([])
            elif not target_pattern:
                target.match_regex = ""
                target.match_regex_operator = "or"
                target.match_rule_ids_json = dump_rule_ids([])
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
