from __future__ import annotations

from ..shared import (
    ModelGroupEnsureFromSiteRequest,
    ModelGroupEnsureFromSiteResponse,
    ModelGroupEnsureResultItem,
    ModelGroupEntity,
    SiteEntity,
    select,
)
from ._group_ensure_operations import _GroupEnsureOperationsMixin
from ._group_ensure_prepare import (
    _EnsureGroupOperation,
    _GroupEnsurePreparationMixin,
)


class _GroupEnsureMixin(
    _GroupEnsurePreparationMixin,
    _GroupEnsureOperationsMixin,
):
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
