from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..shared import (
    AsyncSession,
    ModelGroupEnsureFromSiteRequest,
    ModelGroupEnsureFromSiteResponse,
    ModelGroupEnsureModelInput,
    ModelGroupEnsureResultItem,
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelGroupItemInput,
    ProtocolKind,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    _dump_group_protocols,
    _normalize_group_protocols,
    _parse_group_protocols,
    _parse_runtime_channel_id,
    _parse_supported_protocols_json,
    _runtime_channel_id,
    can_reach_protocol,
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
    items: list[_EnsurePreparedItem] = field(default_factory=list)


@dataclass
class _EnsureSiteLookups:
    protocol_configs: dict[str, SiteProtocolConfigEntity]
    base_url_enabled: dict[str, bool]
    credential_enabled: dict[str, bool]
    model_enabled: dict[tuple[str, str, str, ProtocolKind], bool]


class _GroupEnsureMixin:
    async def _ensure_groups_from_site(
        self, payload: ModelGroupEnsureFromSiteRequest
    ) -> ModelGroupEnsureFromSiteResponse:
        """Plan or apply model group changes from selected site models."""
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
            is_protocol_extension_required = (
                bool(missing_protocols) and not can_use_current_protocols
            )
            if is_protocol_extension_required and not allow_protocol_extension:
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
                if is_protocol_extension_required and allow_protocol_extension
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

            has_protocol_extensions = bool(extended_protocols)
            result_items.append(
                self._ensure_result_item(
                    item,
                    status=(
                        "update"
                        if item_additions or has_protocol_extensions
                        else "unchanged"
                    ),
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
