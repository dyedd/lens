from __future__ import annotations

from .shared import (
    AsyncSession,
    ModelGroupItemEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteProtocolConfigEntity,
    _channel_id_matches_protocol_config,
    delete,
    or_,
    select,
)


class ChannelCleanupMixin:
    async def _cleanup_deleted_protocol_configs(
        self, session: AsyncSession, protocol_config_ids: set[str]
    ) -> None:
        if not protocol_config_ids:
            return
        await session.execute(
            delete(ModelGroupItemEntity).where(
                or_(
                    *[
                        _channel_id_matches_protocol_config(
                            ModelGroupItemEntity.channel_id,
                            protocol_config_id,
                        )
                        for protocol_config_id in protocol_config_ids
                    ]
                )
            )
        )
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

    async def _cleanup_invalid_group_items(
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
            .where(SiteDiscoveredModelEntity.enabled == 1)
            .exists()
        )
        await session.execute(
            delete(ModelGroupItemEntity)
            .where(
                or_(
                    *[
                        _channel_id_matches_protocol_config(
                            ModelGroupItemEntity.channel_id,
                            protocol_config_id,
                        )
                        for protocol_config_id in protocol_config_ids
                    ]
                )
            )
            .where(~matching_model)
        )
