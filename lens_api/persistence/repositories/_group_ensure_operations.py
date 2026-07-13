from __future__ import annotations

from ..shared import (
    AsyncSession,
    ModelGroupEnsureFromSiteResponse,
    ModelGroupEnsureResultItem,
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelGroupItemInput,
    ProtocolKind,
    _dump_group_protocols,
    _normalize_group_protocols,
    _parse_group_protocols,
    _parse_runtime_channel_id,
    can_reach_protocol,
    select,
    uuid,
)
from ._group_ensure_prepare import (
    _EnsureGroupOperation,
    _EnsurePreparedItem,
    _EnsureStatus,
)


class _GroupEnsureOperationsMixin:
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
