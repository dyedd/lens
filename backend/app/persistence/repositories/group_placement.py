from __future__ import annotations

import re
import uuid
from collections import defaultdict

from sqlalchemy import select

from app.models.channels import ChannelConfig
from app.models.model_groups import (
    ModelGroupPlacementResponse,
    ModelGroupView,
    UnplacedModelProvider,
    UnplacedModelView,
)
from app.models.protocols import RoutingStrategy
from app.persistence.entities import ModelGroupEntity
from app.persistence.group_rule_codec import dump_match_models

from .group_read import list_ready_channel_items

# Mirrors the model_groups.name column length.
_MAX_GROUP_NAME_LENGTH = 120


def model_match_key(name: str) -> str:
    """Return the punctuation- and case-insensitive key used to spot near names."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_unplaced_models(
    groups: list[ModelGroupView], channels: list[ChannelConfig]
) -> list[UnplacedModelView]:
    """Return READY channel model names that no execution group covers."""
    execution_groups = [group for group in groups if not group.route_group_id]
    covered_names = {
        item.model_name for group in execution_groups for item in group.items
    }
    groups_by_key: dict[str, list[ModelGroupView]] = defaultdict(list)
    for group in groups:
        for key in {
            model_match_key(group.name),
            *(model_match_key(name) for name in group.match_models),
            *(model_match_key(item.model_name) for item in group.items),
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


def _is_placeable(view: UnplacedModelView) -> bool:
    return (
        not view.similar_group_ids
        and not view.similar_model_names
        and len(view.model_name) <= _MAX_GROUP_NAME_LENGTH
    )


class GroupPlacementMixin:
    async def list_unplaced_models(self) -> list[UnplacedModelView]:
        """Return channel models not covered by any execution group."""
        channels = await self._channel_store.list_channels()
        groups = await self.list_groups(channels=channels)
        return build_unplaced_models(groups, channels)

    async def place_models(
        self, model_names: list[str] | None = None
    ) -> ModelGroupPlacementResponse:
        """Create a failover group for each unplaced model without a near name."""
        channels = await self._channel_store.list_channels()
        requested_names = set(model_names) if model_names is not None else None
        async with self._session_factory() as session:
            entities = list(
                (
                    await session.execute(
                        select(ModelGroupEntity).order_by(ModelGroupEntity.name)
                    )
                )
                .scalars()
                .all()
            )
            groups = await self._hydrate_groups(session, entities, channels)
            unplaced = build_unplaced_models(groups, channels)
            created_entities = [
                ModelGroupEntity(
                    id=str(uuid.uuid4()),
                    name=view.model_name,
                    strategy=RoutingStrategy.FAILOVER.value,
                    route_group_id="",
                    match_models_json=dump_match_models([view.model_name]),
                    match_regex="",
                )
                for view in unplaced
                if _is_placeable(view)
                and (requested_names is None or view.model_name in requested_names)
            ]
            if not created_entities:
                return ModelGroupPlacementResponse(unplaced=unplaced)
            session.add_all(created_entities)
            await session.flush()
            created = await self._hydrate_groups(session, created_entities, channels)
            await session.commit()
        created_names = {group.name for group in created}
        return ModelGroupPlacementResponse(
            created=created,
            unplaced=[
                view for view in unplaced if view.model_name not in created_names
            ],
        )
