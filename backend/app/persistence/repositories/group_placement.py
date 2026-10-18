from __future__ import annotations

import re
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ResourceNotFoundError
from app.models.channels import ChannelConfig
from app.models.model_groups import (
    ModelGroupMemberSource,
    ModelGroupPlacementResponse,
    ModelGroupView,
    UnplacedModelProvider,
    UnplacedModelRemovalResponse,
    UnplacedModelView,
)
from app.models.regex_rules import MAX_REGEX_RULES
from app.persistence.entities import (
    ModelGroupEntity,
    RegexRuleEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)
from app.persistence.regex_rule_references import (
    dump_rule_ids,
    load_rule_patterns,
    parse_rule_ids,
)

from .group_read import list_ready_channel_items

# Mirrors the model_groups.name column length.
MAX_GROUP_NAME_LENGTH = 120


def model_match_key(name: str) -> str:
    """Return the punctuation- and case-insensitive key used to spot near names."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


@dataclass(frozen=True, slots=True)
class GroupCoverage:
    """The names a group claims when spotting unplaced and near-named models."""

    id: str
    name: str
    is_route_group: bool
    # Library rules; when set they replace the name for membership.
    patterns: tuple[re.Pattern[str], ...]
    # Members and exclusions both count: an exclusion is a placement decision.
    model_names: frozenset[str]


def build_group_coverage(
    group: ModelGroupView, patterns: tuple[re.Pattern[str], ...]
) -> GroupCoverage:
    return GroupCoverage(
        id=group.id,
        name=group.name,
        is_route_group=bool(group.route_group_id),
        patterns=patterns,
        model_names=frozenset(
            item.model_name for item in (*group.items, *group.excluded_items)
        ),
    )


def build_unplaced_models(
    groups: Sequence[GroupCoverage], channels: list[ChannelConfig]
) -> list[UnplacedModelView]:
    """Return READY channel model names that no execution group covers."""
    covered_keys = {
        name.casefold()
        for group in groups
        if not group.is_route_group
        for name in group.model_names
    }
    cover_patterns = [
        pattern
        for group in groups
        if not group.is_route_group
        for pattern in group.patterns
    ]

    def is_covered(model_name: str) -> bool:
        return model_name.casefold() in covered_keys or any(
            pattern.search(model_name) for pattern in cover_patterns
        )

    groups_by_key: dict[str, list[GroupCoverage]] = defaultdict(list)
    for group in groups:
        for key in {
            model_match_key(group.name),
            *(model_match_key(name) for name in group.model_names),
        }:
            groups_by_key[key].append(group)

    providers_by_name: dict[str, dict[tuple[str, str], UnplacedModelProvider]] = (
        defaultdict(dict)
    )
    for item in list_ready_channel_items(channels):
        if is_covered(item.model_name):
            continue
        provider = providers_by_name[item.model_name].setdefault(
            (item.protocol_config_id, item.credential_id),
            UnplacedModelProvider(
                site_id=item.site_id or "",
                channel_name=item.channel_name,
                credential_id=item.credential_id,
                credential_name=item.credential_name,
                credential_number=item.credential_number,
                credential_mask=item.credential_mask,
                base_url=item.base_url,
            ),
        )
        if item.protocol is not None and item.protocol not in provider.protocols:
            provider.protocols.append(item.protocol)

    names_by_key: dict[str, list[str]] = defaultdict(list)
    for name in sorted(providers_by_name):
        names_by_key[model_match_key(name)].append(name)
    views: list[UnplacedModelView] = []
    for name in sorted(providers_by_name):
        key = model_match_key(name)
        similar_groups = sorted(groups_by_key.get(key, []), key=lambda g: g.name)
        views.append(
            UnplacedModelView(
                model_name=name,
                match_key=key,
                similar_group_ids=[group.id for group in similar_groups],
                similar_group_names=[group.name for group in similar_groups],
                similar_model_names=[
                    other for other in names_by_key[key] if other != name
                ],
                providers=list(providers_by_name[name].values()),
            )
        )
    return views


def is_placeable_as_new_group(view: UnplacedModelView) -> bool:
    return (
        not view.similar_group_ids
        and not view.similar_model_names
        and len(view.model_name) <= MAX_GROUP_NAME_LENGTH
    )


class GroupPlacementMixin:
    async def list_unplaced_models(self) -> list[UnplacedModelView]:
        """Return channel models not covered by any execution group."""
        channels = await self._channel_store.list_channels()
        groups = await self.list_groups(channels=channels)
        async with self._session_factory() as session:
            patterns = await load_rule_patterns(
                session,
                [rule_id for group in groups for rule_id in group.match_rule_ids],
            )
        return build_unplaced_models(
            [
                build_group_coverage(
                    group,
                    tuple(
                        patterns[rule_id]
                        for rule_id in group.match_rule_ids
                        if rule_id in patterns
                    ),
                )
                for group in groups
            ],
            channels,
        )

    async def place_models(
        self, model_names: list[str] | None = None, group_id: str = ""
    ) -> ModelGroupPlacementResponse:
        """Join same-named groups or create own groups for unplaced models."""
        if group_id:
            return await self._place_models_into_group(model_names or [], group_id)
        if model_names is None:
            model_names = [
                item.model_name for item in await self.list_unplaced_models()
            ]
        report = await self.reconcile_group_members(placement_names=set(model_names))
        created_ids = {group.id for group in report.created_groups}
        groups = await self.list_groups()
        return ModelGroupPlacementResponse(
            created=[group for group in groups if group.id in created_ids],
            joined=[
                change
                for change in report.added
                if change.source == ModelGroupMemberSource.PLACEMENT
                and change.group_id not in created_ids
            ],
            unplaced=report.pending,
        )

    async def _place_models_into_group(
        self, model_names: list[str], group_id: str
    ) -> ModelGroupPlacementResponse:
        """Save the given names as members of an existing execution group."""
        names = [name.strip() for name in model_names if name.strip()]
        if not names:
            raise ValueError("At least one model name is required")
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise ResourceNotFoundError(group_id)
            if entity.route_group_id.strip():
                raise ValueError("Route groups cannot receive members directly")
        report = await self.reconcile_group_members(
            placement_names=set(names), into_group_id=group_id
        )
        return ModelGroupPlacementResponse(
            created=[],
            joined=[change for change in report.added if change.group_id == group_id],
            unplaced=report.pending,
        )

    async def remove_unplaced_models(
        self, model_names: list[str], *, exclude: bool = False
    ) -> UnplacedModelRemovalResponse:
        """Remove unplaced model names from every channel that still offers them.

        ``exclude`` also references ``^name$`` exclude rules on the owning
        sites, so the next sync does not onboard the removed names again.
        """
        names = set(model_names)
        unplaced_names = {view.model_name for view in await self.list_unplaced_models()}
        if covered := sorted(names - unplaced_names):
            raise ValueError(
                "Models are still placed in model groups or not offered: "
                + ", ".join(covered)
            )
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(SiteDiscoveredModelEntity, SiteProtocolConfigEntity.site_id)
                    .join(
                        SiteProtocolConfigEntity,
                        SiteProtocolConfigEntity.id
                        == SiteDiscoveredModelEntity.protocol_config_id,
                    )
                    .where(SiteDiscoveredModelEntity.model_name.in_(names))
                    .where(SiteDiscoveredModelEntity.enabled == 1)
                )
            ).all()
            deleted = 0
            names_by_site: dict[str, set[str]] = defaultdict(set)
            for entity, site_id in rows:
                if exclude:
                    names_by_site[site_id].add(entity.model_name)
                await session.delete(entity)
                deleted += 1
            excluded = 0
            for site_id, site_names in names_by_site.items():
                excluded += await _add_site_exclude_rules(session, site_id, site_names)
            await session.commit()
        return UnplacedModelRemovalResponse(deleted=deleted, excluded=excluded)


_REGEX_SPECIAL_CHARS = frozenset(".^$*+?{}[]" + chr(92) + "|()")


def _exclude_pattern(name: str) -> str:
    """Anchored literal pattern; escapes the same characters as the frontend."""
    escaped = "".join(
        chr(92) + char if char in _REGEX_SPECIAL_CHARS else char for char in name
    )
    return "^" + escaped + "$"


async def _add_site_exclude_rules(
    session: AsyncSession, site_id: str, names: set[str]
) -> int:
    """Reference ``^name$`` exclude rules so a sync never onboards them again."""
    site = await session.get(SiteEntity, site_id)
    if site is None:
        return 0
    referenced = parse_rule_ids(site.model_sync_exclude_rule_ids_json)
    rule_rows = (
        await session.execute(
            select(RegexRuleEntity.id, RegexRuleEntity.name, RegexRuleEntity.pattern)
        )
    ).all()
    existing_by_pattern = {row.pattern: row.id for row in rule_rows}
    taken_names = {row.name.casefold() for row in rule_rows}
    added = 0
    for name in sorted(names):
        pattern = _exclude_pattern(name)
        rule_id = existing_by_pattern.get(pattern)
        if rule_id is None:
            if len(rule_rows) + added >= MAX_REGEX_RULES:
                raise ValueError(f"At most {MAX_REGEX_RULES} regex rules are allowed")
            rule_id = str(uuid.uuid4())
            base_name = f"排除：{name}"[:60]
            rule_name = base_name
            suffix = 2
            while rule_name.casefold() in taken_names:
                suffix_text = f" ({suffix})"
                rule_name = f"{base_name[: 60 - len(suffix_text)]}{suffix_text}"
                suffix += 1
            taken_names.add(rule_name.casefold())
            existing_by_pattern[pattern] = rule_id
            session.add(
                RegexRuleEntity(
                    id=rule_id,
                    name=rule_name,
                    pattern=pattern,
                    description="删除模型时生成，阻止同步再次自动接入",
                )
            )
        if rule_id not in referenced:
            referenced.append(rule_id)
            added += 1
    if added:
        site.model_sync_exclude_rule_ids_json = dump_rule_ids(referenced)
    return added
