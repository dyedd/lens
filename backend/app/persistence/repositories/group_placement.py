from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.model_group_matching import (
    MatchRegexOperator,
    matches_model_group,
)
from app.models.channels import ChannelConfig
from app.models.model_groups import (
    ModelGroupView,
    UnplacedModelProvider,
    UnplacedModelView,
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
    # The group's own regex combines with its name according to this operator.
    patterns: tuple[re.Pattern[str], ...]
    match_regex_operator: MatchRegexOperator
    # Members and exclusions both count: an exclusion is a placement decision.
    model_names: frozenset[str]


def build_group_coverage(
    group: ModelGroupView,
    patterns: tuple[re.Pattern[str], ...],
    match_regex_operator: MatchRegexOperator = "or",
) -> GroupCoverage:
    return GroupCoverage(
        id=group.id,
        name=group.name,
        is_route_group=bool(group.route_group_id),
        patterns=patterns,
        match_regex_operator=match_regex_operator,
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

    def is_covered(model_name: str) -> bool:
        return model_name.casefold() in covered_keys or any(
            not group.is_route_group
            and matches_model_group(
                group.name,
                model_name,
                group.patterns,
                group.match_regex_operator,
            )
            for group in groups
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
            (item.site_id or item.protocol_config_id, item.credential_id),
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
