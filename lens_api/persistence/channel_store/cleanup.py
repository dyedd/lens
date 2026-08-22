from __future__ import annotations

from ...core.protocol_reachability import can_reach_protocol
from ...core.runtime_channel_ids import (
    compose_runtime_channel_id,
    split_runtime_channel_id,
)
from ..shared import _dump_group_protocols, _parse_group_protocols
from .shared import (
    AsyncSession,
    ModelGroupEntity,
    ModelGroupItemEntity,
    ProtocolKind,
    SiteDiscoveredModelEntity,
    SiteProtocolConfigEntity,
    SiteProtocolConfigCredentialEntity,
    SiteProtocolConfigSyncTargetEntity,
    delete,
    select,
)


class ChannelCleanupMixin:
    async def _cleanup_deleted_protocol_configs(
        self, session: AsyncSession, protocol_config_ids: set[str]
    ) -> None:
        if not protocol_config_ids:
            return
        await session.execute(
            delete(SiteDiscoveredModelEntity).where(
                SiteDiscoveredModelEntity.protocol_config_id.in_(protocol_config_ids)
            )
        )
        await session.execute(
            delete(SiteProtocolConfigSyncTargetEntity).where(
                SiteProtocolConfigSyncTargetEntity.protocol_config_id.in_(
                    protocol_config_ids
                )
            )
        )
        await session.execute(
            delete(SiteProtocolConfigCredentialEntity).where(
                SiteProtocolConfigCredentialEntity.protocol_config_id.in_(
                    protocol_config_ids
                )
            )
        )
        await session.execute(
            delete(SiteProtocolConfigEntity).where(
                SiteProtocolConfigEntity.id.in_(protocol_config_ids)
            )
        )

    async def _cleanup_invalid_group_items(
        self, session: AsyncSession, protocol_config_ids: set[str]
    ) -> None:
        """Delete removed members and trim unsupported execution protocols."""
        if not protocol_config_ids:
            return
        matching_model = (
            select(SiteDiscoveredModelEntity.id)
            .where(
                ModelGroupItemEntity.channel_id
                == SiteDiscoveredModelEntity.protocol_config_id.concat("_").concat(
                    SiteDiscoveredModelEntity.protocol
                )
            )
            .where(
                SiteDiscoveredModelEntity.credential_id
                == ModelGroupItemEntity.credential_id
            )
            .where(
                SiteDiscoveredModelEntity.model_name == ModelGroupItemEntity.model_name
            )
            .exists()
        )
        runtime_channel_ids = {
            compose_runtime_channel_id(protocol_config_id, protocol)
            for protocol_config_id in protocol_config_ids
            for protocol in ProtocolKind
        }
        invalid_item_filter = (
            ModelGroupItemEntity.channel_id.in_(runtime_channel_ids) & ~matching_model
        )
        group_ids = set(
            (
                await session.execute(
                    select(ModelGroupItemEntity.group_id)
                    .where(invalid_item_filter)
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        await session.execute(delete(ModelGroupItemEntity).where(invalid_item_filter))
        if not group_ids:
            return

        groups = (
            (
                await session.execute(
                    select(ModelGroupEntity).where(
                        ModelGroupEntity.id.in_(group_ids),
                        ModelGroupEntity.route_group_id == "",
                    )
                )
            )
            .scalars()
            .all()
        )
        member_rows = (
            await session.execute(
                select(
                    ModelGroupItemEntity.group_id,
                    ModelGroupItemEntity.channel_id,
                ).where(ModelGroupItemEntity.group_id.in_(group_ids))
            )
        ).all()
        protocols_by_group: dict[str, set[ProtocolKind]] = {}
        for group_id, channel_id in member_rows:
            parsed = split_runtime_channel_id(channel_id)
            if parsed is not None:
                protocols_by_group.setdefault(group_id, set()).add(parsed[1])
        for group in groups:
            remaining_protocols = protocols_by_group.get(group.id, set())
            if not remaining_protocols:
                continue
            current_protocols = _parse_group_protocols(group)
            next_protocols = [
                protocol
                for protocol in current_protocols
                if any(
                    can_reach_protocol(member_protocol, protocol)
                    for member_protocol in remaining_protocols
                )
            ]
            if next_protocols and next_protocols != current_protocols:
                group.protocols_json = _dump_group_protocols(next_protocols)
