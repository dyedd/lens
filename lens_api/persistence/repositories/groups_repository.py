from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Literal

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..shared import (
    AsyncSession,
    ChannelStatus,
    ModelGroup,
    ModelGroupCandidateItem,
    ModelGroupCandidatesRequest,
    ModelGroupCandidatesResponse,
    ModelGroupCreate,
    ModelGroupEntity,
    ModelGroupEnsureFromSiteRequest,
    ModelGroupEnsureFromSiteResponse,
    ModelGroupEnsureModelInput,
    ModelGroupEnsureResultItem,
    ModelGroupItem,
    ModelGroupItemEntity,
    ModelGroupItemInput,
    ModelGroupUpdate,
    ModelPriceEntity,
    ProtocolKind,
    REQUEST_LOG_TERMINAL_STATUSES,
    RequestLogEntity,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    _channel_ids_by_protocol_config,
    _dump_group_protocols,
    _group_supports_protocol,
    _normalize_group_protocols,
    _parse_group_protocols,
    _parse_runtime_channel_id,
    _parse_supported_protocols_json,
    _runtime_channel_id,
    can_reach_protocol,
    delete,
    func,
    normalize_model_key,
    select,
    uuid,
)

_EnsureStatus = Literal["create", "update", "unchanged", "skipped"]


@dataclass
class _EnsurePreparedItem:
    group_name: str
    protocol_config_id: str
    credential_id: str
    model_name: str
    protocols: list[ProtocolKind]
    items: list[ModelGroupItemInput]


@dataclass
class _EnsureGroupOperation:
    group_name: str
    entity: ModelGroupEntity | None = None
    items: list[_EnsurePreparedItem] = dc_field(default_factory=list)


@dataclass
class _EnsureSiteLookups:
    protocol_configs: dict[str, SiteProtocolConfigEntity]
    base_url_enabled: dict[str, bool]
    credential_enabled: dict[str, bool]
    model_enabled: dict[tuple[str, str, str, ProtocolKind], bool]


class GroupRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_groups(self) -> list[ModelGroup]:
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
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)
            hydrated = await self._hydrate_groups(session, [entity])
            return hydrated[0]

    async def find_group_by_name(
        self, protocol: str, name: str | None
    ) -> ModelGroup | None:
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
        from ..channel_store import ChannelStore

        channel_store = ChannelStore(self._session_factory)
        all_channels = await channel_store.list()

        protocols_filter: list[ProtocolKind] = list(dict.fromkeys(payload.protocols))

        excluded_model_ids: set[tuple[str, str, str]] = set()
        for item in payload.exclude_items:
            parsed = _parse_runtime_channel_id(item.channel_id)
            if parsed is not None:
                excluded_protocol_config_id, _ = parsed
                excluded_model_ids.add(
                    (excluded_protocol_config_id, item.credential_id, item.model_name)
                )

        @dataclass
        class _CandidateAggregate:
            native_protocols: list[ProtocolKind] = dc_field(default_factory=list)
            protocol_channels: dict[ProtocolKind, str] = dc_field(default_factory=dict)
            channel_name: str = ""
            credential_name: str = ""
            base_url: str = ""
            model_name: str = ""
            credential_id: str = ""
            protocol_config_id: str = ""

        candidate_aggregates: dict[tuple[str, str, str], _CandidateAggregate] = {}

        for channel in all_channels:
            if channel.status.value != "enabled":
                continue
            parsed = _parse_runtime_channel_id(channel.id)
            if parsed is None:
                continue
            protocol_config_id, native_protocol = parsed

            enabled_credential_ids: set[str] = {
                key.id for key in channel.keys if key.enabled
            }

            for model in channel.models:
                if not model.enabled:
                    continue
                if model.credential_id not in enabled_credential_ids:
                    continue

                model_key = (protocol_config_id, model.credential_id, model.model_name)
                if model_key not in candidate_aggregates:
                    candidate_aggregates[model_key] = _CandidateAggregate(
                        protocol_config_id=protocol_config_id,
                        credential_id=model.credential_id,
                        credential_name=model.credential_name,
                        model_name=model.model_name,
                        channel_name=channel.name,
                        base_url=str(channel.base_url),
                    )
                aggregate = candidate_aggregates[model_key]
                if native_protocol not in aggregate.native_protocols:
                    aggregate.native_protocols.append(native_protocol)
                if native_protocol not in aggregate.protocol_channels:
                    aggregate.protocol_channels[native_protocol] = channel.id

        candidates: list[ModelGroupCandidateItem] = []

        for model_key, aggregate in candidate_aggregates.items():
            protocol_config_id, credential_id, model_name = model_key

            if protocols_filter:
                if not all(
                    any(can_reach_protocol(q, p) for q in aggregate.native_protocols)
                    for p in protocols_filter
                ):
                    continue

            if model_key in excluded_model_ids:
                continue

            rep_protocol: ProtocolKind = aggregate.native_protocols[0]
            if protocols_filter:
                for p in protocols_filter:
                    if p in aggregate.protocol_channels:
                        rep_protocol = p
                        break
            rep_channel_id = aggregate.protocol_channels.get(
                rep_protocol, next(iter(aggregate.protocol_channels.values()))
            )

            recommended_items: list[ModelGroupItemInput] = []
            if protocols_filter:
                chosen: dict[str, ModelGroupItemInput] = {}
                uncovered: list[ProtocolKind] = []
                for p in protocols_filter:
                    if p in aggregate.protocol_channels:
                        cid = aggregate.protocol_channels[p]
                        if cid not in chosen:
                            chosen[cid] = ModelGroupItemInput(
                                channel_id=cid,
                                credential_id=credential_id,
                                model_name=model_name,
                                enabled=True,
                            )
                    else:
                        uncovered.append(p)
                for p in uncovered:
                    fallback_native = next(
                        (
                            q
                            for q in aggregate.native_protocols
                            if can_reach_protocol(q, p)
                        ),
                        None,
                    )
                    if fallback_native is not None:
                        cid = aggregate.protocol_channels[fallback_native]
                        chosen.setdefault(
                            cid,
                            ModelGroupItemInput(
                                channel_id=cid,
                                credential_id=credential_id,
                                model_name=model_name,
                                enabled=True,
                            ),
                        )
                recommended_items = list(chosen.values())

            candidates.append(
                ModelGroupCandidateItem(
                    site_id="",
                    channel_id=rep_channel_id,
                    channel_name=aggregate.channel_name,
                    protocol=rep_protocol,
                    credential_id=credential_id,
                    credential_name=aggregate.credential_name,
                    credential_number=0,
                    base_url=aggregate.base_url,
                    model_name=model_name,
                    protocol_config_id=protocol_config_id,
                    protocols=sorted(aggregate.native_protocols, key=lambda p: p.value),
                    protocol_channels=aggregate.protocol_channels,
                    items=recommended_items,
                )
            )

        candidates.sort(key=lambda c: (c.channel_name, c.model_name))

        return ModelGroupCandidatesResponse(candidates=candidates)

    async def ensure_groups_from_site(
        self, payload: ModelGroupEnsureFromSiteRequest
    ) -> ModelGroupEnsureFromSiteResponse:
        async with self._session_factory() as session:
            site = await session.get(SiteEntity, payload.site_id)
            if site is None:
                raise KeyError(payload.site_id)

            lookups = await self._load_ensure_site_lookups(session, payload.site_id)
            result_items: list[ModelGroupEnsureResultItem] = []
            operations_by_group: dict[str, _EnsureGroupOperation] = {}
            seen_selection_keys: set[
                tuple[str, str, str, str, tuple[ProtocolKind, ...]]
            ] = set()

            for item in payload.models:
                prepared, skipped = self._prepare_ensure_model_item(item, lookups)
                if skipped is not None:
                    result_items.append(skipped)
                    continue

                selection_key = (
                    prepared.group_name,
                    prepared.protocol_config_id,
                    prepared.credential_id,
                    prepared.model_name,
                    tuple(sorted(prepared.protocols)),
                )
                if selection_key in seen_selection_keys:
                    result_items.append(
                        self._ensure_result_item(
                            prepared,
                            status="skipped",
                            skipped_reason="duplicate_selection",
                        )
                    )
                    continue
                seen_selection_keys.add(selection_key)

                operation = operations_by_group.setdefault(
                    prepared.group_name,
                    _EnsureGroupOperation(group_name=prepared.group_name),
                )
                operation.items.append(prepared)

            if operations_by_group:
                rows = (
                    (
                        await session.execute(
                            select(ModelGroupEntity).where(
                                ModelGroupEntity.name.in_(
                                    list(operations_by_group.keys())
                                )
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                for row in rows:
                    operation = operations_by_group.get(row.name)
                    if operation is not None:
                        operation.entity = row

            for operation in operations_by_group.values():
                if operation.entity is None:
                    result_items.extend(
                        await self._ensure_create_group_operation(
                            session, operation, dry_run=payload.dry_run
                        )
                    )
                    continue
                if operation.entity.route_group_id.strip():
                    result_items.extend(
                        self._ensure_result_item(
                            item,
                            status="skipped",
                            group_id=operation.entity.id,
                            skipped_reason="route_group",
                        )
                        for item in operation.items
                    )
                    continue
                result_items.extend(
                    await self._ensure_update_group_operation(
                        session,
                        operation,
                        dry_run=payload.dry_run,
                        allow_protocol_extension=payload.allow_protocol_extension,
                    )
                )

            if not payload.dry_run:
                await session.commit()

            return self._ensure_response(payload.dry_run, result_items)

    async def _load_ensure_site_lookups(
        self, session: AsyncSession, site_id: str
    ) -> _EnsureSiteLookups:
        protocol_rows = (
            (
                await session.execute(
                    select(SiteProtocolConfigEntity).where(
                        SiteProtocolConfigEntity.site_id == site_id
                    )
                )
            )
            .scalars()
            .all()
        )
        base_url_rows = (
            (
                await session.execute(
                    select(SiteBaseUrlEntity).where(
                        SiteBaseUrlEntity.site_id == site_id
                    )
                )
            )
            .scalars()
            .all()
        )
        credential_rows = (
            (
                await session.execute(
                    select(SiteCredentialEntity).where(
                        SiteCredentialEntity.site_id == site_id
                    )
                )
            )
            .scalars()
            .all()
        )

        protocol_config_ids = [row.id for row in protocol_rows]
        model_rows: list[SiteDiscoveredModelEntity] = []
        if protocol_config_ids:
            model_rows = (
                (
                    await session.execute(
                        select(SiteDiscoveredModelEntity).where(
                            SiteDiscoveredModelEntity.protocol_config_id.in_(
                                protocol_config_ids
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )

        model_enabled: dict[tuple[str, str, str, ProtocolKind], bool] = {}
        for row in model_rows:
            if not row.protocol:
                continue
            try:
                protocol = ProtocolKind(row.protocol)
            except ValueError:
                continue
            model_enabled[
                (row.protocol_config_id, row.credential_id, row.model_name, protocol)
            ] = bool(row.enabled)

        return _EnsureSiteLookups(
            protocol_configs={row.id: row for row in protocol_rows},
            base_url_enabled={row.id: bool(row.enabled) for row in base_url_rows},
            credential_enabled={row.id: bool(row.enabled) for row in credential_rows},
            model_enabled=model_enabled,
        )

    def _prepare_ensure_model_item(
        self,
        item: ModelGroupEnsureModelInput,
        lookups: _EnsureSiteLookups,
    ) -> tuple[_EnsurePreparedItem, None] | tuple[None, ModelGroupEnsureResultItem]:
        model_name = item.model_name.strip()
        group_name = item.group_name.strip() or model_name
        protocols = list(dict.fromkeys(item.protocols))
        prepared = _EnsurePreparedItem(
            group_name=group_name,
            protocol_config_id=item.protocol_config_id,
            credential_id=item.credential_id,
            model_name=model_name,
            protocols=protocols,
            items=[],
        )
        if not model_name:
            return None, self._ensure_result_item(
                prepared, status="skipped", skipped_reason="model_name_required"
            )

        protocol_config = lookups.protocol_configs.get(item.protocol_config_id)
        if protocol_config is None:
            return None, self._ensure_result_item(
                prepared,
                status="skipped",
                skipped_reason="protocol_config_not_found",
            )
        if not protocol_config.enabled or not lookups.base_url_enabled.get(
            protocol_config.base_url_id, False
        ):
            return None, self._ensure_result_item(
                prepared, status="skipped", skipped_reason="channel_disabled"
            )

        credential_enabled = lookups.credential_enabled.get(item.credential_id)
        if credential_enabled is None:
            return None, self._ensure_result_item(
                prepared, status="skipped", skipped_reason="credential_not_found"
            )
        if not credential_enabled:
            return None, self._ensure_result_item(
                prepared, status="skipped", skipped_reason="credential_disabled"
            )

        configured_protocols = set(
            _parse_supported_protocols_json(protocol_config.protocols_json)
        )
        valid_protocols: list[ProtocolKind] = []
        members: list[ModelGroupItemInput] = []
        for protocol in protocols:
            if protocol not in configured_protocols:
                continue
            model_key = (
                item.protocol_config_id,
                item.credential_id,
                model_name,
                protocol,
            )
            if lookups.model_enabled.get(model_key) is not True:
                continue
            valid_protocols.append(protocol)
            members.append(
                ModelGroupItemInput(
                    channel_id=_runtime_channel_id(item.protocol_config_id, protocol),
                    credential_id=item.credential_id,
                    model_name=model_name,
                    enabled=True,
                )
            )

        if not members:
            return None, self._ensure_result_item(
                prepared, status="skipped", skipped_reason="model_not_available"
            )

        prepared.protocols = valid_protocols
        prepared.items = members
        return prepared, None

    async def _ensure_create_group_operation(
        self,
        session: AsyncSession,
        operation: _EnsureGroupOperation,
        *,
        dry_run: bool,
    ) -> list[ModelGroupEnsureResultItem]:
        protocols = self._ensure_operation_protocols(operation.items)
        members = self._ensure_operation_members(operation.items)
        group_id = ""
        if not dry_run:
            entity = ModelGroupEntity(
                id=str(uuid.uuid4()),
                name=operation.group_name,
                protocols_json=_dump_group_protocols(protocols),
                strategy="round_robin",
                route_group_id="",
                sync_filter_mode="",
                sync_filter_query="",
            )
            session.add(entity)
            await session.flush()
            self._replace_group_items(session, entity.id, members)
            group_id = entity.id

        return [
            self._ensure_result_item(
                item,
                status="create",
                group_id=group_id,
                added_count=len(item.items),
            )
            for item in operation.items
        ]

    async def _ensure_update_group_operation(
        self,
        session: AsyncSession,
        operation: _EnsureGroupOperation,
        *,
        dry_run: bool,
        allow_protocol_extension: bool,
    ) -> list[ModelGroupEnsureResultItem]:
        entity = operation.entity
        current_protocols = _normalize_group_protocols(_parse_group_protocols(entity))
        next_protocols = list(current_protocols)

        current_rows = (
            (
                await session.execute(
                    select(ModelGroupItemEntity)
                    .where(ModelGroupItemEntity.group_id == entity.id)
                    .order_by(
                        ModelGroupItemEntity.sort_order.asc(),
                        ModelGroupItemEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        existing_keys = {
            self._ensure_member_key(row.channel_id, row.credential_id, row.model_name)
            for row in current_rows
        }
        pending_keys = set(existing_keys)
        additions: list[ModelGroupItemInput] = []
        result_items: list[ModelGroupEnsureResultItem] = []

        for item in operation.items:
            missing_protocols = [
                protocol
                for protocol in item.protocols
                if protocol not in current_protocols
            ]
            can_use_current_protocols = any(
                self._ensure_member_reaches_protocols(member, current_protocols)
                for member in item.items
            )
            must_extend_protocols = (
                bool(missing_protocols) and not can_use_current_protocols
            )
            if must_extend_protocols and not allow_protocol_extension:
                result_items.append(
                    self._ensure_result_item(
                        item,
                        status="skipped",
                        group_id=entity.id,
                        skipped_reason="protocol_extension_required",
                        missing_protocols=missing_protocols,
                    )
                )
                continue

            extended_protocols = (
                missing_protocols
                if must_extend_protocols and allow_protocol_extension
                else []
            )
            if extended_protocols:
                for protocol in extended_protocols:
                    if protocol not in next_protocols:
                        next_protocols.append(protocol)

            item_members = [
                member
                for member in item.items
                if self._ensure_member_reaches_protocols(member, next_protocols)
            ]
            item_additions: list[ModelGroupItemInput] = []
            for member in item_members:
                member_key = self._ensure_member_key(
                    member.channel_id, member.credential_id, member.model_name
                )
                if member_key in pending_keys:
                    continue
                pending_keys.add(member_key)
                item_additions.append(member)
            additions.extend(item_additions)

            adds_protocol = bool(extended_protocols)
            result_items.append(
                self._ensure_result_item(
                    item,
                    status="update" if item_additions or adds_protocol else "unchanged",
                    group_id=entity.id,
                    added_count=len(item_additions),
                    existing_count=len(item_members) - len(item_additions),
                    missing_protocols=extended_protocols,
                )
            )

        if not dry_run:
            if next_protocols != current_protocols:
                entity.protocols_json = _dump_group_protocols(next_protocols)
            for index, member in enumerate(additions, start=len(current_rows)):
                session.add(
                    ModelGroupItemEntity(
                        group_id=entity.id,
                        channel_id=member.channel_id,
                        credential_id=member.credential_id,
                        model_name=member.model_name,
                        enabled=1 if member.enabled else 0,
                        sort_order=index,
                    )
                )

        return result_items

    @staticmethod
    def _ensure_operation_protocols(
        items: list[_EnsurePreparedItem],
    ) -> list[ProtocolKind]:
        protocols: list[ProtocolKind] = []
        for item in items:
            for protocol in item.protocols:
                if protocol not in protocols:
                    protocols.append(protocol)
        return protocols

    @classmethod
    def _ensure_operation_members(
        cls, items: list[_EnsurePreparedItem]
    ) -> list[ModelGroupItemInput]:
        members: list[ModelGroupItemInput] = []
        seen: set[tuple[str, str, str]] = set()
        for item in items:
            for member in item.items:
                member_key = cls._ensure_member_key(
                    member.channel_id, member.credential_id, member.model_name
                )
                if member_key in seen:
                    continue
                seen.add(member_key)
                members.append(member)
        return members

    @staticmethod
    def _ensure_member_key(
        channel_id: str, credential_id: str, model_name: str
    ) -> tuple[str, str, str]:
        return channel_id, credential_id, model_name

    @staticmethod
    def _ensure_member_reaches_protocols(
        member: ModelGroupItemInput, protocols: list[ProtocolKind]
    ) -> bool:
        parsed = _parse_runtime_channel_id(member.channel_id)
        if parsed is None:
            return False
        _, native_protocol = parsed
        return any(
            can_reach_protocol(native_protocol, protocol) for protocol in protocols
        )

    @staticmethod
    def _ensure_result_item(
        item: _EnsurePreparedItem,
        *,
        status: _EnsureStatus,
        group_id: str = "",
        added_count: int = 0,
        existing_count: int = 0,
        skipped_reason: str = "",
        missing_protocols: list[ProtocolKind] | None = None,
    ) -> ModelGroupEnsureResultItem:
        return ModelGroupEnsureResultItem(
            group_id=group_id,
            group_name=item.group_name,
            protocol_config_id=item.protocol_config_id,
            credential_id=item.credential_id,
            model_name=item.model_name,
            protocols=item.protocols,
            status=status,
            added_count=added_count,
            existing_count=existing_count,
            skipped_reason=skipped_reason,
            missing_protocols=missing_protocols or [],
        )

    @staticmethod
    def _ensure_response(
        dry_run: bool, items: list[ModelGroupEnsureResultItem]
    ) -> ModelGroupEnsureFromSiteResponse:
        return ModelGroupEnsureFromSiteResponse(
            dry_run=dry_run,
            created_count=sum(1 for item in items if item.status == "create"),
            updated_count=sum(1 for item in items if item.status == "update"),
            unchanged_count=sum(1 for item in items if item.status == "unchanged"),
            skipped_count=sum(1 for item in items if item.status == "skipped"),
            items=items,
        )

    async def create_group(self, payload: ModelGroupCreate) -> ModelGroup:
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

    async def _validate_group_payload(
        self,
        session: AsyncSession,
        name: str,
        protocols: list[ProtocolKind],
        route_group_id: str = "",
        items: list[ModelGroupItemInput] | None = None,
        exclude_group_id: str | None = None,
    ) -> ModelGroupEntity | None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Model group name is required")
        normalized_protocols = _normalize_group_protocols(protocols)

        result = await session.execute(
            select(ModelGroupEntity.id)
            .where(ModelGroupEntity.name == normalized_name)
            .limit(1)
        )
        existing_id = result.scalar_one_or_none()
        if existing_id is not None and existing_id != exclude_group_id:
            raise ValueError(f"Model group already exists: {normalized_name}")

        normalized_route_group_id = route_group_id.strip()
        route_group: ModelGroupEntity | None = None
        if normalized_route_group_id:
            if (
                exclude_group_id is not None
                and normalized_route_group_id == exclude_group_id
            ):
                raise ValueError("Model group cannot route to itself")
            route_group = await session.get(ModelGroupEntity, normalized_route_group_id)
            if route_group is None:
                raise ValueError(
                    f"Route target model group not found: {normalized_route_group_id}"
                )
            route_group_protocols = set(_parse_group_protocols(route_group))
            missing_protocols = [
                protocol
                for protocol in normalized_protocols
                if protocol not in route_group_protocols
            ]
            if missing_protocols:
                missing = ", ".join(protocol.value for protocol in missing_protocols)
                raise ValueError(
                    f"Route target protocols must cover source protocols: {missing}"
                )
            if route_group.route_group_id.strip():
                raise ValueError(
                    f"Route target must be an execution group: {route_group.name}"
                )

        normalized_items = items or []
        if not normalized_items:
            return route_group

        from ..channel_store import ChannelStore

        channel_store = ChannelStore(self._session_factory)
        all_channels = await channel_store.list()
        channel_by_id = {ch.id: ch for ch in all_channels}

        channel_ids = list(dict.fromkeys(item.channel_id for item in normalized_items))
        missing_channel_ids = [cid for cid in channel_ids if cid not in channel_by_id]
        if missing_channel_ids:
            raise ValueError(f"Channels not found: {', '.join(missing_channel_ids)}")

        for item in normalized_items:
            ch = channel_by_id[item.channel_id]
            credential_ids_in_channel = {key.id for key in ch.keys}
            if item.credential_id not in credential_ids_in_channel:
                raise ValueError(
                    f"Credential not found in channel {item.channel_id}: "
                    f"{item.credential_id}"
                )

        for item in normalized_items:
            if not item.enabled:
                continue
            member_channel = channel_by_id[item.channel_id]
            if member_channel.status != ChannelStatus.ENABLED:
                raise ValueError(
                    f"Channel '{member_channel.name}' is disabled; "
                    "enable the channel before enabling its members"
                )
            enabled_credential_ids = {
                key.id for key in member_channel.keys if key.enabled
            }
            if item.credential_id not in enabled_credential_ids:
                raise ValueError(
                    "Credential is disabled; enable it before enabling this member"
                )

        invalid_channel_ids = [
            cid
            for cid in channel_ids
            if not any(
                can_reach_protocol(channel_by_id[cid].protocol, protocol)
                for protocol in normalized_protocols
            )
        ]
        if invalid_channel_ids:
            raise ValueError(
                "Channels cannot reach any selected protocol: "
                + ", ".join(invalid_channel_ids)
            )

        item_protocols = [
            channel_by_id[item.channel_id].protocol for item in normalized_items
        ]
        for protocol in normalized_protocols:
            if not any(
                can_reach_protocol(item_protocol, protocol)
                for item_protocol in item_protocols
            ):
                raise ValueError(
                    f"Protocol {protocol.value} has no reachable channel in group items"
                )

        model_names_by_channel: dict[str, set[tuple[str, str]]] = {}
        for cid in channel_ids:
            ch = channel_by_id.get(cid)
            if ch:
                model_names_by_channel[cid] = {
                    (m.credential_id, m.model_name) for m in ch.models
                }

        for item in normalized_items:
            channel_models = model_names_by_channel.get(item.channel_id, set())
            target = (item.credential_id, item.model_name)
            if target not in channel_models:
                raise ValueError(
                    f"Model not found in channel {item.channel_id} credential={item.credential_id}: {item.model_name}"
                )

        return route_group

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
        (
            channel_site_names,
            protocol_by_channel_id,
            credential_names_by_channel,
            credential_numbers,
        ) = await self._load_group_item_channel_lookups(session, channel_ids)
        for row in rows:
            items_by_group.setdefault(row.group_id, []).append(
                ModelGroupItem(
                    channel_id=row.channel_id,
                    channel_name=channel_site_names.get(row.channel_id, ""),
                    protocol=protocol_by_channel_id.get(row.channel_id),
                    credential_id=row.credential_id,
                    credential_name=credential_names_by_channel.get(
                        row.channel_id, {}
                    ).get(row.credential_id, ""),
                    credential_number=credential_numbers.get(row.channel_id, {}).get(
                        row.credential_id, 0
                    ),
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
    ) -> tuple[
        dict[str, str],
        dict[str, ProtocolKind],
        dict[str, dict[str, str]],
        dict[str, dict[str, int]],
    ]:
        (
            channels_by_protocol_config,
            protocol_by_channel_id,
        ) = _channel_ids_by_protocol_config(channel_ids)
        if not channels_by_protocol_config:
            return {}, {}, {}, {}

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
        return (
            channel_site_names,
            protocol_by_channel_id,
            credential_names_by_channel,
            credential_numbers_by_channel,
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

    async def list_group_names(self, *, include_routed: bool = False) -> list[str]:
        from ..shared import ModelGroupEntity, select

        async with self._session_factory() as session:
            query = select(ModelGroupEntity.name).order_by(ModelGroupEntity.name.asc())
            if not include_routed:
                query = query.where(ModelGroupEntity.route_group_id == "")
            rows = await session.execute(query)
            return [str(item) for item in rows.scalars().all() if str(item).strip()]
