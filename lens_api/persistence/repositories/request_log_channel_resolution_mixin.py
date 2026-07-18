from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..shared import (
    GatewayApiKeyEntity,
    RequestLogEntity,
    RequestLogItem,
    SiteDiscoveredModelEntity,
    SiteProtocolConfigEntity,
    _channel_ids_by_protocol_config,
    select,
)


class RequestLogChannelResolutionMixin:
    async def _hydrate_request_logs(
        self,
        session: AsyncSession,
        entities: list[RequestLogEntity],
        *,
        gateway_has_multiple_keys: bool | None = None,
    ) -> list[RequestLogItem]:
        remarks = await self._gateway_key_repo._gateway_key_remarks_by_id(
            session, [entity.gateway_key_id for entity in entities]
        )
        if gateway_has_multiple_keys is None:
            gateway_has_multiple_keys = (
                await self._gateway_has_multiple_keys(session) if entities else False
            )
        credential_counts = await self._request_log_channel_credential_counts(
            session, [entity.channel_id for entity in entities]
        )
        return [
            self._to_request_log(
                entity,
                gateway_key_remark=remarks.get(entity.gateway_key_id or ""),
                gateway_has_multiple_keys=gateway_has_multiple_keys,
                channel_has_multiple_credentials=(
                    credential_counts.get(entity.channel_id or "", 0) > 1
                ),
            )
            for entity in entities
        ]

    @staticmethod
    async def _gateway_has_multiple_keys(session: AsyncSession) -> bool:
        rows = (await session.execute(select(GatewayApiKeyEntity.id).limit(2))).all()
        return len(rows) > 1

    async def _request_log_channel_credential_counts(
        self, session: AsyncSession, channel_ids: list[str | None]
    ) -> dict[str, int]:
        (
            channels_by_protocol_config,
            protocol_by_channel_id,
        ) = _channel_ids_by_protocol_config(channel_ids)

        if not channels_by_protocol_config:
            return {}

        protocol_config_ids = list(channels_by_protocol_config.keys())
        credentials_by_channel: dict[str, set[str]] = {
            channel_id: set()
            for channel_ids_for_protocol_config in channels_by_protocol_config.values()
            for channel_id in channel_ids_for_protocol_config
        }

        default_credential_rows = (
            await session.execute(
                select(
                    SiteProtocolConfigEntity.id,
                    SiteProtocolConfigEntity.credential_id,
                ).where(SiteProtocolConfigEntity.id.in_(protocol_config_ids))
            )
        ).all()
        for protocol_config_id, credential_id in default_credential_rows:
            if not credential_id:
                continue
            for channel_id in channels_by_protocol_config.get(
                str(protocol_config_id), []
            ):
                credentials_by_channel[channel_id].add(str(credential_id))

        model_credential_rows = (
            await session.execute(
                select(
                    SiteDiscoveredModelEntity.protocol_config_id,
                    SiteDiscoveredModelEntity.credential_id,
                    SiteDiscoveredModelEntity.protocol,
                ).where(
                    SiteDiscoveredModelEntity.protocol_config_id.in_(
                        protocol_config_ids
                    )
                )
            )
        ).all()
        for protocol_config_id, credential_id, model_protocol in model_credential_rows:
            if not credential_id:
                continue
            for channel_id in channels_by_protocol_config.get(
                str(protocol_config_id), []
            ):
                channel_protocol = protocol_by_channel_id.get(channel_id)
                if model_protocol is None:
                    continue
                if (
                    channel_protocol is not None
                    and str(model_protocol) != channel_protocol.value
                ):
                    continue
                credentials_by_channel[channel_id].add(str(credential_id))

        return {
            channel_id: len(credential_ids)
            for channel_id, credential_ids in credentials_by_channel.items()
        }
