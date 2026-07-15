from __future__ import annotations

from ...core.runtime_channel_ids import compose_runtime_channel_id
from .shared import (
    AsyncSession,
    ModelGroupEntity,
    ModelGroupItemEntity,
    ProtocolKind,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteProtocolConfigEntity,
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
            delete(SiteProtocolConfigEntity).where(
                SiteProtocolConfigEntity.id.in_(protocol_config_ids)
            )
        )

    async def _cleanup_deleted_credentials(
        self, session: AsyncSession, credential_ids: set[str]
    ) -> None:
        if not credential_ids:
            return
        await session.execute(
            delete(SiteCredentialEntity).where(
                SiteCredentialEntity.id.in_(credential_ids)
            )
        )

    async def _cleanup_invalid_synced_group_items(
        self, session: AsyncSession, protocol_config_ids: set[str]
    ) -> None:
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
        synced_group = (
            select(ModelGroupEntity.id)
            .where(ModelGroupEntity.id == ModelGroupItemEntity.group_id)
            .where(ModelGroupEntity.sync_filter_mode != "")
            .exists()
        )
        runtime_channel_ids = {
            compose_runtime_channel_id(protocol_config_id, protocol)
            for protocol_config_id in protocol_config_ids
            for protocol in ProtocolKind
        }
        await session.execute(
            delete(ModelGroupItemEntity)
            .where(ModelGroupItemEntity.channel_id.in_(runtime_channel_ids))
            .where(synced_group)
            .where(~matching_model)
        )
