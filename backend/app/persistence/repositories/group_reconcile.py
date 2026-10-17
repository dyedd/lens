"""Reconcile saved model group members with names, placement, and upstream state.

One pass runs the group stages of the model pipeline in order: models join the
group named after them, unplaced models join a same-named group or get a new
one, and members whose model stayed missing upstream past a grace period
retire. Every member it adds is saved, so reads and routing never infer
membership from names themselves.
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    ModelGroupNewMemberPosition,
    ModelGroupOrigin,
    ModelGroupReconcileReport,
    ModelGroupRefView,
)
from app.models.protocols import RoutingStrategy
from app.persistence.entities import ModelGroupEntity, ModelGroupItemEntity
from app.persistence.group_rule_codec import parse_fallback_group_ids
from app.persistence.regex_rule_references import load_rule_patterns, parse_rule_ids

from .group_placement import (
    GroupCoverage,
    build_unplaced_models,
    is_placeable_as_new_group,
)
from .group_read import list_ready_channel_items

# How long a synced model may stay missing upstream before its members leave
# their groups. Until then they stay listed and routing skips them.
UPSTREAM_MISSING_RETIRE_AFTER = timedelta(days=7)

_AUTO_SOURCES = frozenset(
    {ModelGroupMemberSource.RULE, ModelGroupMemberSource.PLACEMENT}
)

type MemberKey = tuple[str, str, str]
# An exclusion covers every protocol channel of one credential's model, so a
# protocol added to the site later does not bring the model back.
type ExclusionKey = tuple[str, str, str]


def _naive_utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _matches_group(state: _GroupMemberState, names: list[str]) -> bool:
    """Whether the group's rules, or its name, accept any of a model's aliases."""
    if state.patterns:
        return any(pattern.search(name) for pattern in state.patterns for name in names)
    name_key = state.entity.name.casefold()
    return any(name.casefold() == name_key for name in names)


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
    # Library rules; when set they replace name matching for this group.
    patterns: tuple[re.Pattern[str], ...]
    # Members in route order; exclusions are kept apart and never reordered.
    members: list[ModelGroupItemEntity]
    excluded: list[ModelGroupItemEntity]
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

    def rate_of(self, row: ModelGroupItemEntity) -> float:
        lookup = self.lookups.get(row.channel_id)
        credential = lookup.credentials_by_id.get(row.credential_id) if lookup else None
        if credential is None or credential.rate_multiplier is None:
            return math.inf
        return credential.rate_multiplier

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
        """Save READY channel items as members at the group's insert position."""
        existing_keys = state.keys()
        exclusion_keys = state.exclusion_keys()
        position = ModelGroupNewMemberPosition(state.entity.new_member_position)
        start_index = 0
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
            if position == ModelGroupNewMemberPosition.START:
                state.members.insert(start_index, row)
                start_index += 1
            elif position == ModelGroupNewMemberPosition.RATE_ASC:
                rate = self.rate_of(row)
                index = next(
                    (
                        index
                        for index, member in enumerate(state.members)
                        if self.rate_of(member) > rate
                    ),
                    len(state.members),
                )
                state.members.insert(index, row)
            else:
                state.members.append(row)
            state.is_reordered = True
            self.has_writes = True
            self.report.added.append(self.describe(state, row))


class GroupReconcileMixin:
    async def reconcile_group_members(
        self,
        *,
        synced_targets: set[tuple[str, str]] | None = None,
        placement_names: set[str] | None = None,
        into_group_id: str | None = None,
    ) -> ModelGroupReconcileReport:
        """Save name-matched members, place uncovered models, retire missing ones.

        ``synced_targets`` holds the ``(protocol_config_id, credential_id)``
        pairs a model sync just fetched; only their members can retire.
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
            if synced_targets:
                self._retire_missing_members(run, synced_targets, _naive_utc_now())
            await self._remove_empty_auto_groups(run)
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
        rule_patterns = await load_rule_patterns(
            session,
            (
                rule_id
                for entity in entities
                for rule_id in parse_rule_ids(entity.match_rule_ids_json)
            ),
        )
        groups = {
            entity.id: _GroupMemberState(
                entity=entity,
                patterns=tuple(
                    rule_patterns[rule_id]
                    for rule_id in parse_rule_ids(entity.match_rule_ids_json)
                    if rule_id in rule_patterns
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
                lookup = run.lookups.get(row.channel_id)
                channel_model = (
                    lookup.models_by_key.get((row.credential_id, row.model_name))
                    if lookup is not None
                    else None
                )
                aliases = (
                    list(channel_model.match_aliases) or [row.model_name]
                    if channel_model is not None
                    else [row.model_name]
                )
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
                if dead_target or not _matches_group(state, aliases):
                    run.report.removed.append(run.describe(state, row))
                    run.delete(state, row)
            run.add(
                state,
                [
                    item
                    for item in run.ready_items
                    if _matches_group(state, item.match_aliases or [item.model_name])
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
                model_names=state.model_names(),
            )
            for state in run.groups.values()
        ] + [
            GroupCoverage(
                id=entity.id,
                name=entity.name,
                is_route_group=True,
                patterns=(),
                model_names=frozenset(),
            )
            for entity in route_groups
        ]
        groups_by_name = {
            state.entity.name.casefold(): state for state in run.groups.values()
        }
        target = run.groups.get(into_group_id) if into_group_id else None
        item_name_keys = {
            id(item): {
                name.casefold() for name in (item.match_aliases or [item.model_name])
            }
            for item in run.ready_items
        }
        for view in build_unplaced_models(coverage, channels):
            is_requested = placement_names is None or view.model_name in placement_names
            if not is_requested:
                run.report.pending.append(view)
                continue
            view_names = view.match_aliases or [view.model_name]
            view_name_keys = {name.casefold() for name in view_names}
            items = [
                item
                for item in run.ready_items
                if item_name_keys[id(item)] & view_name_keys
            ]
            if target is not None:
                run.add(target, items, ModelGroupMemberSource.PLACEMENT)
                continue
            same_named = next(
                (
                    groups_by_name[key]
                    for key in view_name_keys
                    if key in groups_by_name
                ),
                None,
            )
            # A group with rules decides membership alone, never by its name.
            if same_named is not None and not same_named.patterns:
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
                new_member_position=ModelGroupNewMemberPosition.END.value,
                origin=ModelGroupOrigin.AUTO.value,
            )
            run.session.add(entity)
            state = _GroupMemberState(
                entity=entity, patterns=(), members=[], excluded=[]
            )
            run.groups[entity.id] = state
            groups_by_name[entity.name.casefold()] = state
            run.has_writes = True
            run.report.created_groups.append(
                ModelGroupRefView(id=entity.id, name=entity.name)
            )
            # The group is named after the model, so the new group takes it.
            run.add(state, items, ModelGroupMemberSource.PLACEMENT)

    @staticmethod
    def _retire_missing_members(
        run: _ReconcileRun,
        synced_targets: set[tuple[str, str]],
        now: datetime,
    ) -> None:
        """Remove members whose model stayed missing past the grace period.

        Before that the member stays saved and routing skips it as
        unavailable; a sync that finds the model again clears the miss.
        """
        retire_before = now - UPSTREAM_MISSING_RETIRE_AFTER
        for state in run.groups.values():
            for row in list(state.members):
                if (
                    protocol_config_id_from_runtime_channel_id(row.channel_id),
                    row.credential_id,
                ) not in synced_targets:
                    continue
                lookup = run.lookups.get(row.channel_id)
                model = (
                    lookup.models_by_key.get((row.credential_id, row.model_name))
                    if lookup
                    else None
                )
                if (
                    model is None
                    or not model.upstream_missing
                    or model.upstream_missing_since is None
                    or model.upstream_missing_since > retire_before
                ):
                    continue
                run.report.retired.append(run.describe(state, row))
                run.delete(state, row)

    @staticmethod
    async def _remove_empty_auto_groups(run: _ReconcileRun) -> None:
        """Delete auto-created groups that lost every member and exclusion."""
        referenced_ids: set[str] = set()
        for state in run.groups.values():
            # Groups created in this pass are unflushed, so the column
            # defaults have not been applied to them yet.
            fallback_json = state.entity.fallback_group_ids_json or "[]"
            referenced_ids.update(parse_fallback_group_ids(fallback_json))
        candidates = [
            state
            for state in run.groups.values()
            if state.entity.origin == ModelGroupOrigin.AUTO.value
            and not state.members
            and not state.excluded
            and state.entity.id not in referenced_ids
        ]
        if not candidates:
            return
        candidate_ids = {state.entity.id for state in candidates}
        route_rows = await run.session.execute(
            select(ModelGroupEntity.route_group_id).where(
                ModelGroupEntity.route_group_id.in_(candidate_ids)
            )
        )
        route_referenced = {row[0] for row in route_rows.all()}
        for state in candidates:
            if state.entity.id in route_referenced:
                continue
            run.groups.pop(state.entity.id, None)
            await run.session.delete(state.entity)
            run.has_writes = True
