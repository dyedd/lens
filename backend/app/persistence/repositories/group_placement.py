from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import delete, select

from app.models.channels import ChannelConfig
from app.models.model_groups import (
    ModelGroupMemberSource,
    ModelGroupPlacementResponse,
    ModelGroupView,
    UnplacedModelProvider,
    UnplacedModelRemovalResponse,
    UnplacedModelView,
)
from app.persistence.entities import (
    SiteDiscoveredModelEntity,
    SiteProtocolConfigEntity,
    SiteProtocolConfigSyncTargetEntity,
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
    match_models: tuple[str, ...]
    # Members and exclusions both count: an exclusion is a placement decision.
    model_names: frozenset[str]


def build_group_coverage(group: ModelGroupView) -> GroupCoverage:
    return GroupCoverage(
        id=group.id,
        name=group.name,
        is_route_group=bool(group.route_group_id),
        match_models=tuple(group.match_models),
        model_names=frozenset(
            item.model_name for item in (*group.items, *group.excluded_items)
        ),
    )


def build_unplaced_models(
    groups: Sequence[GroupCoverage], channels: list[ChannelConfig]
) -> list[UnplacedModelView]:
    """Return READY channel model names that no execution group covers."""
    covered_names = {
        name
        for group in groups
        if not group.is_route_group
        for name in group.model_names
    }
    groups_by_key: dict[str, list[GroupCoverage]] = defaultdict(list)
    for group in groups:
        for key in {
            model_match_key(group.name),
            *(model_match_key(name) for name in group.match_models),
            *(model_match_key(name) for name in group.model_names),
        }:
            groups_by_key[key].append(group)

    providers_by_name: dict[str, dict[tuple[str, str], UnplacedModelProvider]] = (
        defaultdict(dict)
    )
    for item in list_ready_channel_items(channels):
        if item.model_name in covered_names:
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
        return build_unplaced_models(
            [build_group_coverage(group) for group in groups], channels
        )

    async def place_models(
        self, model_names: list[str] | None = None
    ) -> ModelGroupPlacementResponse:
        """Join or create groups for unplaced models without a near name."""
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

    async def remove_unplaced_models(
        self, model_names: list[str]
    ) -> UnplacedModelRemovalResponse:
        """Remove unplaced model names from every channel that still offers them.

        Remove the materialized row and its sync target. A deleted synced
        model must not return on the next upstream refresh.
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
                (
                    await session.execute(
                        select(SiteDiscoveredModelEntity)
                        .join(
                            SiteProtocolConfigEntity,
                            SiteProtocolConfigEntity.id
                            == SiteDiscoveredModelEntity.protocol_config_id,
                        )
                        .where(SiteDiscoveredModelEntity.model_name.in_(names))
                        .where(SiteDiscoveredModelEntity.enabled == 1)
                    )
                )
                .scalars()
                .all()
            )
            deleted = 0
            for entity in rows:
                await session.execute(
                    delete(SiteProtocolConfigSyncTargetEntity).where(
                        SiteProtocolConfigSyncTargetEntity.protocol_config_id
                        == entity.protocol_config_id,
                        SiteProtocolConfigSyncTargetEntity.credential_id
                        == entity.credential_id,
                        SiteProtocolConfigSyncTargetEntity.protocol == entity.protocol,
                        SiteProtocolConfigSyncTargetEntity.model_name
                        == entity.model_name,
                    )
                )
                await session.delete(entity)
                deleted += 1
            await session.commit()
        return UnplacedModelRemovalResponse(deleted=deleted)
