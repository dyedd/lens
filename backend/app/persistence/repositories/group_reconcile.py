"""Reconcile saved model group members with rules, placement, and upstream state.

One pass runs the group stages of the model pipeline in order: rule members
join or leave, unplaced models join a same-named group or get a new one, and
members whose model stayed missing upstream past a grace period retire. Every
member it adds is saved, so reads and routing never match rules themselves.
"""

from __future__ import annotations

import math
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
    ModelGroupReconcileReport,
    ModelGroupRefView,
)
from app.models.protocols import RoutingStrategy
from app.persistence.entities import ModelGroupEntity, ModelGroupItemEntity
from app.persistence.group_match_rules import (
    GroupMatchRules,
    build_group_match_rules,
    load_group_match_rules,
)
from app.persistence.group_rule_codec import dump_match_models, parse_match_models

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
    rules: GroupMatchRules
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
    ) -> ModelGroupReconcileReport:
        """Save rule members, place uncovered models, and retire missing ones.

        ``synced_targets`` holds the ``(protocol_config_id, credential_id)``
        pairs a model sync just fetched; only their members can retire.
        ``placement_names`` limits which unplaced models may join or create a
        group; every other stage still runs.
        """
        channels = await self._channel_store.list_channels()
        async with self._session_factory() as session:
            run = await self._start_reconcile_run(session, channels)
            self._sync_rule_members(run)
            await self._place_uncovered_models(run, channels, placement_names)
            if synced_targets:
                self._retire_missing_members(run, synced_targets, _naive_utc_now())
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
        rules_by_group = await load_group_match_rules(session, entities)
        groups = {
            entity.id: _GroupMemberState(
                entity=entity,
                rules=rules_by_group[entity.id],
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
    def _sync_rule_members(run: _ReconcileRun) -> None:
        """Drop automatic members that lost their rule or target, add new matches."""
        for state in run.groups.values():
            for row in list(state.members):
                source = ModelGroupMemberSource(row.source)
                if source not in _AUTO_SOURCES:
                    continue
                lost_rule = (
                    source == ModelGroupMemberSource.RULE
                    and not state.rules.matches(row.model_name)
                )
                lost_target = (
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
                if lost_rule or lost_target:
                    run.report.removed.append(run.describe(state, row))
                    run.delete(state, row)
            if state.rules.is_empty:
                continue
            run.add(
                state,
                [
                    item
                    for item in run.ready_items
                    if state.rules.matches(item.model_name)
                ],
                ModelGroupMemberSource.RULE,
            )

    async def _place_uncovered_models(
        self,
        run: _ReconcileRun,
        channels: list[ChannelConfig],
        placement_names: set[str] | None,
    ) -> None:
        """Join a same-named group or create one; near names wait for a person."""
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
                match_models=tuple(parse_match_models(state.entity.match_models_json)),
                model_names=state.model_names(),
            )
            for state in run.groups.values()
        ] + [
            GroupCoverage(
                id=entity.id,
                name=entity.name,
                is_route_group=True,
                match_models=(),
                model_names=frozenset(),
            )
            for entity in route_groups
        ]
        groups_by_name = {
            state.entity.name.casefold(): state for state in run.groups.values()
        }
        for view in build_unplaced_models(coverage, channels):
            is_requested = placement_names is None or view.model_name in placement_names
            same_named = groups_by_name.get(view.model_name.casefold())
            items = [
                item for item in run.ready_items if item.model_name == view.model_name
            ]
            if is_requested and same_named is not None:
                run.add(same_named, items, ModelGroupMemberSource.PLACEMENT)
                continue
            if not is_requested or not is_placeable_as_new_group(view):
                run.report.pending.append(view)
                continue
            entity = ModelGroupEntity(
                id=str(uuid.uuid4()),
                name=view.model_name,
                strategy=RoutingStrategy.FAILOVER.value,
                route_group_id="",
                match_models_json=dump_match_models([view.model_name]),
                new_member_position=ModelGroupNewMemberPosition.END.value,
            )
            run.session.add(entity)
            state = _GroupMemberState(
                entity=entity,
                rules=build_group_match_rules([view.model_name], [], {}),
                members=[],
                excluded=[],
            )
            run.groups[entity.id] = state
            groups_by_name[entity.name.casefold()] = state
            run.has_writes = True
            run.report.created_groups.append(
                ModelGroupRefView(id=entity.id, name=entity.name)
            )
            # The new group matches its own name, so its members follow that rule.
            run.add(state, items, ModelGroupMemberSource.RULE)

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
