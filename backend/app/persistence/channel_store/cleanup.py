from __future__ import annotations

from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.protocols import ProtocolKind
from app.persistence.entities import (
    ModelGroupItemEntity,
    SiteDiscoveredModelEntity,
    SiteProtocolConfigCredentialEntity,
    SiteProtocolConfigEntity,
    SiteProtocolConfigSyncTargetEntity,
)

from ...core.runtime_channel_ids import compose_runtime_channel_id


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
        """Delete members that no longer resolve to configured models."""
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
