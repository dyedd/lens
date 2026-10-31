"""Reconcile saved model group members with names, placement, and upstream state.

One pass runs the group stages of the model pipeline in order: models join the
group named after them, unplaced models join a same-named group or get a new
one, and members whose target is no longer available are removed when they
were joined automatically. Every member it adds is saved, so reads and
routing never infer membership from names themselves.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_group_matching import (
    MatchRegexOperator,
    compile_model_group_pattern,
    matches_model_group,
)
from app.core.model_group_status import (
    ModelGroupChannelLookup,
    build_model_group_channel_lookups,
    evaluate_model_group_item,
)
from app.core.runtime_channel_ids import protocol_config_id_from_runtime_channel_id
from app.models.channels import ChannelConfig
from app.models.model_groups import (
    ModelGroupItemInput,
    ModelGroupItemState,
    ModelGroupItemView,
    ModelGroupMemberChangeView,
    ModelGroupMemberSource,
    ModelGroupReconcileReport,
    ModelGroupRefView,
)
from app.models.protocols import RoutingStrategy
from app.persistence.entities import ModelGroupEntity, ModelGroupItemEntity

from .group_placement import (
    GroupCoverage,
    build_unplaced_models,
    is_placeable_as_new_group,
)
from .group_read import list_ready_channel_items

_AUTO_SOURCES = frozenset(
    {ModelGroupMemberSource.RULE, ModelGroupMemberSource.PLACEMENT}
)

type MemberKey = tuple[str, str, str]
# An exclusion covers every protocol channel of one credential's model, so a
# protocol added to the site later does not bring the model back.
type ExclusionKey = tuple[str, str, str]


def _matches_group(state: _GroupMemberState, model_name: str) -> bool:
    """Whether the group's name and current inline rules accept a model name."""
    return matches_model_group(
        state.entity.name, model_name, state.patterns, state.match_regex_operator
    )


def _row_key(row: ModelGroupItemEntity) -> MemberKey:
    return row.channel_id, row.credential_id, row.model_name


def _exclusion_key(
    channel_id: str, credential_id: str, model_name: str
) -> ExclusionKey:
    return (
        protocol_config_id_from_runtime_channel_id(channel_id),
        credential_id,
        model_name,
    )


@dataclass(slots=True)
class _GroupMemberState:
    entity: ModelGroupEntity
    # The group's own regex combines with its name according to this operator.
    patterns: tuple[re.Pattern[str], ...]
    # Members in route order; exclusions are kept apart and never reordered.
    members: list[ModelGroupItemEntity]
    excluded: list[ModelGroupItemEntity]
    match_regex_operator: MatchRegexOperator = "or"
    is_reordered: bool = False

    def keys(self) -> set[MemberKey]:
        return {_row_key(row) for row in (*self.members, *self.excluded)}

    def exclusion_keys(self) -> set[ExclusionKey]:
        return {_exclusion_key(*_row_key(row)) for row in self.excluded}

    def model_names(self) -> frozenset[str]:
        return frozenset(row.model_name for row in (*self.members, *self.excluded))


@dataclass(slots=True)
class _ReconcileRun:
    session: AsyncSession
    lookups: dict[str, ModelGroupChannelLookup]
    ready_items: list[ModelGroupItemView]
    groups: dict[str, _GroupMemberState]
    report: ModelGroupReconcileReport = field(default_factory=ModelGroupReconcileReport)
    deleted_rows: list[ModelGroupItemEntity] = field(default_factory=list)
    has_writes: bool = False

    def describe(
        self,
        state: _GroupMemberState,
        row: ModelGroupItemEntity,
    ) -> ModelGroupMemberChangeView:
        lookup = self.lookups.get(row.channel_id)
        credential = lookup.credentials_by_id.get(row.credential_id) if lookup else None
        return ModelGroupMemberChangeView(
            group_id=state.entity.id,
            group_name=state.entity.name,
            channel_id=row.channel_id,
            channel_name=lookup.channel.name if lookup else "",
            credential_id=row.credential_id,
            credential_name=credential.remark if credential else "",
            model_name=row.model_name,
            source=ModelGroupMemberSource(row.source),
        )

    def delete(self, state: _GroupMemberState, row: ModelGroupItemEntity) -> None:
        state.members.remove(row)
        self.deleted_rows.append(row)
        state.is_reordered = True
        self.has_writes = True

    def add(
        self,
        state: _GroupMemberState,
        items: list[ModelGroupItemView],
        source: ModelGroupMemberSource,
    ) -> None:
        """Save READY channel items as members at the end of the group."""
        existing_keys = state.keys()
        exclusion_keys = state.exclusion_keys()
        for item in items:
            key = (item.channel_id, item.credential_id, item.model_name)
            if key in existing_keys or _exclusion_key(*key) in exclusion_keys:
                continue
            deleted = next(
                (
                    row
                    for row in self.deleted_rows
                    if row.group_id == state.entity.id and _row_key(row) == key
                ),
                None,
            )
            if deleted is not None:
                self.deleted_rows.remove(deleted)
                deleted.source = source.value
                deleted.excluded = 0
                self.report.removed[:] = [
                    change
                    for change in self.report.removed
                    if (
                        change.group_id,
                        change.channel_id,
                        change.credential_id,
                        change.model_name,
                    )
                    != (state.entity.id, *key)
                ]
                state.members.append(deleted)
                existing_keys.add(key)
                state.is_reordered = True
                continue
            existing_keys.add(key)
            row = ModelGroupItemEntity(
                group_id=state.entity.id,
                channel_id=item.channel_id,
                credential_id=item.credential_id,
                model_name=item.model_name,
                enabled=1,
                source=source.value,
                excluded=0,
                sort_order=0,
            )
            self.session.add(row)
            state.members.append(row)
            state.is_reordered = True
            self.has_writes = True
            self.report.added.append(self.describe(state, row))


class GroupReconcileMixin:
    async def reconcile_group_members(
        self,
        *,
        placement_names: set[str] | None = None,
        into_group_id: str | None = None,
    ) -> ModelGroupReconcileReport:
        """Save name-matched members and place uncovered models.

        ``placement_names`` limits which unplaced models may join or create a
        group; every other stage still runs. ``into_group_id`` sends those
        names into one existing execution group instead of same-named ones.
        """
        channels = await self._channel_store.list_channels()
        async with self._session_factory() as session:
            run = await self._start_reconcile_run(session, channels)
            self._join_matching_members(run)
            await self._place_uncovered_models(
                run, channels, placement_names, into_group_id
            )
            for row in run.deleted_rows:
                await session.delete(row)
            for state in run.groups.values():
                if state.is_reordered:
                    for index, row in enumerate(state.members):
                        row.sort_order = index
            if run.has_writes:
                await session.commit()
        return run.report

    async def _start_reconcile_run(
        self, session: AsyncSession, channels: list[ChannelConfig]
    ) -> _ReconcileRun:
        entities = list(
            (
                await session.execute(
                    select(ModelGroupEntity)
                    .where(ModelGroupEntity.route_group_id == "")
                    .order_by(ModelGroupEntity.name)
                )
            )
            .scalars()
            .all()
        )
        rows = (
            (
                await session.execute(
                    select(ModelGroupItemEntity)
                    .where(
                        ModelGroupItemEntity.group_id.in_(
                            [entity.id for entity in entities]
                        )
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
        groups = {
            entity.id: _GroupMemberState(
                entity=entity,
                patterns=(
                    (direct_pattern,)
                    if (
                        direct_pattern := compile_model_group_pattern(
                            entity.match_regex
                        )
                    )
                    else ()
                ),
                match_regex_operator=(
                    entity.match_regex_operator
                    if entity.match_regex_operator in {"and", "or"}
                    else "or"
                ),
                members=[],
                excluded=[],
            )
            for entity in entities
        }
        for row in rows:
            state = groups[row.group_id]
            (state.excluded if row.excluded else state.members).append(row)
        return _ReconcileRun(
            session=session,
            lookups=build_model_group_channel_lookups(channels),
            ready_items=list_ready_channel_items(channels),
            groups=groups,
        )

    @staticmethod
    def _join_matching_members(run: _ReconcileRun) -> None:
        """Join the members a group's rules (or its name) match, prune dead ones."""
        for state in run.groups.values():
            for row in list(state.members):
                if ModelGroupMemberSource(row.source) not in _AUTO_SOURCES:
                    continue
                dead_target = (
                    evaluate_model_group_item(
                        ModelGroupItemInput(
                            channel_id=row.channel_id,
                            credential_id=row.credential_id,
                            model_name=row.model_name,
                        ),
                        run.lookups,
                    ).state
                    == ModelGroupItemState.INVALID
                )
                if dead_target or not _matches_group(state, row.model_name):
                    run.report.removed.append(run.describe(state, row))
                    run.delete(state, row)
            run.add(
                state,
                [
                    item
                    for item in run.ready_items
                    if _matches_group(state, item.model_name)
                ],
                ModelGroupMemberSource.PLACEMENT,
            )

    async def _place_uncovered_models(
        self,
        run: _ReconcileRun,
        channels: list[ChannelConfig],
        placement_names: set[str] | None,
        into_group_id: str | None = None,
    ) -> None:
        """Join same-named groups and create own groups for conflict-free models."""
        route_groups = (
            (
                await run.session.execute(
                    select(ModelGroupEntity).where(
                        ModelGroupEntity.route_group_id != ""
                    )
                )
            )
            .scalars()
            .all()
        )
        coverage = [
            GroupCoverage(
                id=state.entity.id,
                name=state.entity.name,
                is_route_group=False,
                patterns=state.patterns,
                match_regex_operator=state.match_regex_operator,
                model_names=state.model_names(),
            )
            for state in run.groups.values()
        ] + [
            GroupCoverage(
                id=entity.id,
                name=entity.name,
                is_route_group=True,
                patterns=(),
                match_regex_operator="or",
                model_names=frozenset(),
            )
            for entity in route_groups
        ]
        groups_by_name = {
            state.entity.name.casefold(): state for state in run.groups.values()
        }
        target = run.groups.get(into_group_id) if into_group_id else None
        item_name_keys = {
            id(item): item.model_name.casefold() for item in run.ready_items
        }
        for view in build_unplaced_models(coverage, channels):
            is_requested = placement_names is None or view.model_name in placement_names
            if not is_requested:
                run.report.pending.append(view)
                continue
            view_name_key = view.model_name.casefold()
            items = [
                item
                for item in run.ready_items
                if item_name_keys[id(item)] == view_name_key
            ]
            if target is not None:
                # An explicit "join this group" is a manual membership: a later
                # reconcile must keep it even when the names differ.
                run.add(target, items, ModelGroupMemberSource.MANUAL)
                continue
            same_named = groups_by_name.get(view_name_key)
            if same_named is not None and any(
                _matches_group(same_named, item.model_name) for item in items
            ):
                run.add(same_named, items, ModelGroupMemberSource.PLACEMENT)
                continue
            if not is_placeable_as_new_group(view):
                run.report.pending.append(view)
                continue
            entity = ModelGroupEntity(
                id=str(uuid.uuid4()),
                name=view.model_name,
                strategy=RoutingStrategy.FAILOVER.value,
                route_group_id="",
                fallback_group_ids_json="[]",
            )
            run.session.add(entity)
            state = _GroupMemberState(
                entity=entity,
                patterns=(),
                match_regex_operator="or",
                members=[],
                excluded=[],
            )
            run.groups[entity.id] = state
            groups_by_name[entity.name.casefold()] = state
            run.has_writes = True
            run.report.created_groups.append(
                ModelGroupRefView(id=entity.id, name=entity.name)
            )
            # The group is named after the model, so the new group takes it.
            run.add(state, items, ModelGroupMemberSource.PLACEMENT)
