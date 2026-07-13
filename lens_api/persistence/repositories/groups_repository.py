from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..shared import (
    AsyncSession,
    ModelGroup,
    ModelGroupCandidatesRequest,
    ModelGroupCandidatesResponse,
    ModelGroupCreate,
    ModelGroupEntity,
    ModelGroupEnsureFromSiteRequest,
    ModelGroupEnsureFromSiteResponse,
    ModelGroupItemEntity,
    ModelGroupItemInput,
    ModelGroupUpdate,
    _dump_group_protocols,
    _group_supports_protocol,
    _normalize_group_protocols,
    _parse_group_protocols,
    delete,
    select,
    uuid,
)
from ._group_candidates import _GroupCandidatesMixin
from ._group_ensure import _GroupEnsureMixin
from ._group_mapping import _GroupMappingMixin
from ._group_validation import _GroupValidationMixin


class GroupRepository(
    _GroupCandidatesMixin,
    _GroupEnsureMixin,
    _GroupValidationMixin,
    _GroupMappingMixin,
):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_groups(self) -> list[ModelGroup]:
        """Return all model groups with hydrated members and pricing."""
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
            return await self._hydrate_groups(session, entities)

    async def get_group(self, group_id: str) -> ModelGroup:
        """Return a model group by identifier or raise when it does not exist."""
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)
            hydrated = await self._hydrate_groups(session, [entity])
            return hydrated[0]

    async def find_group_by_name(
        self, protocol: str, name: str | None
    ) -> ModelGroup | None:
        """Return a named model group when it supports the requested protocol."""
        normalized_name = (name or "").strip()
        if not normalized_name:
            return None

        async with self._session_factory() as session:
            result = await session.execute(
                select(ModelGroupEntity)
                .where(ModelGroupEntity.name == normalized_name)
                .limit(1)
            )
            entity = result.scalar_one_or_none()
            if entity is None or not _group_supports_protocol(entity, protocol):
                return None
            hydrated = await self._hydrate_groups(session, [entity])
            return hydrated[0]

    async def list_group_candidates(
        self, payload: ModelGroupCandidatesRequest
    ) -> ModelGroupCandidatesResponse:
        """Return enabled model candidates reachable for the requested protocols."""
        return await self._list_group_candidates(payload)

    async def ensure_groups_from_site(
        self, payload: ModelGroupEnsureFromSiteRequest
    ) -> ModelGroupEnsureFromSiteResponse:
        """Plan or apply model group changes from selected site models."""
        return await self._ensure_groups_from_site(payload)

    async def create_group(self, payload: ModelGroupCreate) -> ModelGroup:
        """Create and return a validated model group."""
        async with self._session_factory() as session:
            protocols = _normalize_group_protocols(payload.protocols)
            route_group = await self._validate_group_payload(
                session,
                payload.name,
                protocols,
                payload.route_group_id,
                payload.items,
            )
            entity = ModelGroupEntity(
                id=str(uuid.uuid4()),
                name=payload.name.strip(),
                protocols_json=_dump_group_protocols(protocols),
                strategy=payload.strategy.value,
                route_group_id=route_group.id if route_group is not None else "",
                sync_filter_mode=payload.sync_filter_mode.value,
                sync_filter_query=payload.sync_filter_query,
            )
            session.add(entity)
            await session.flush()
            self._replace_group_items(session, entity.id, payload.items)
            await session.commit()
            await session.refresh(entity)
            hydrated = await self._hydrate_groups(session, [entity])
            return hydrated[0]

    async def update_group(
        self, group_id: str, payload: ModelGroupUpdate
    ) -> ModelGroup:
        """Update and return an existing model group."""
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)

            current_protocols = _normalize_group_protocols(
                _parse_group_protocols(entity)
            )
            next_protocols = _normalize_group_protocols(
                payload.protocols or current_protocols
            )
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
            if (
                payload.protocols is not None
                and has_inbound_route_group
                and set(current_protocols) - set(next_protocols)
            ):
                raise ValueError(
                    "Execution groups referenced by route groups cannot remove protocols"
                )
            if next_route_group_id and has_inbound_route_group:
                raise ValueError(
                    "Execution groups referenced by route groups cannot become route groups"
                )
            current_items = await self._load_group_items(session, [group_id])
            next_items = (
                payload.items
                if payload.items is not None
                else [
                    ModelGroupItemInput(
                        channel_id=item.channel_id,
                        credential_id=item.credential_id,
                        model_name=item.model_name,
                        enabled=item.enabled,
                    )
                    for item in current_items.get(group_id, [])
                ]
            )
            route_group = await self._validate_group_payload(
                session,
                next_name,
                next_protocols,
                next_route_group_id,
                next_items,
                exclude_group_id=group_id,
            )

            changes = payload.model_dump(exclude_unset=True)
            for key, value in changes.items():
                if key == "protocols":
                    if value is not None:
                        entity.protocols_json = _dump_group_protocols(next_protocols)
                elif key == "strategy" and value is not None:
                    entity.strategy = value.value
                elif key == "sync_filter_mode" and value is not None:
                    entity.sync_filter_mode = value.value
                elif key == "items":
                    continue
                elif key == "route_group_id":
                    entity.route_group_id = (
                        route_group.id if route_group is not None else ""
                    )
                    if not entity.route_group_id:
                        continue
                    entity.sync_filter_mode = ""
                    entity.sync_filter_query = ""
                else:
                    setattr(entity, key, value)

            if entity.route_group_id:
                entity.sync_filter_mode = ""
                entity.sync_filter_query = ""

            if payload.items is not None or payload.protocols is not None:
                await session.execute(
                    delete(ModelGroupItemEntity).where(
                        ModelGroupItemEntity.group_id == group_id
                    )
                )
                self._replace_group_items(session, group_id, next_items)

            await session.commit()
            await session.refresh(entity)
            hydrated = await self._hydrate_groups(session, [entity])
            return hydrated[0]

    async def delete_group(self, group_id: str) -> None:
        """Delete an unreferenced model group and its members."""
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)
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

    async def list_group_names(self, *, include_routed: bool = False) -> list[str]:
        """Return model group names, optionally including routed groups."""
        from ..shared import ModelGroupEntity, select

        async with self._session_factory() as session:
            query = select(ModelGroupEntity.name).order_by(ModelGroupEntity.name.asc())
            if not include_routed:
                query = query.where(ModelGroupEntity.route_group_id == "")
            rows = await session.execute(query)
            return [str(item) for item in rows.scalars().all() if str(item).strip()]
