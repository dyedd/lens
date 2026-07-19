from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..shared import (
    GatewayApiKeyEntity,
    RequestLogEntity,
    RequestLogItem,
    SiteCredentialEntity,
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
        credential_counts, credential_metadata = (
            await self._request_log_channel_credentials(
                session, [entity.channel_id for entity in entities]
            )
        )
        return [
            self._to_request_log(
                entity,
                gateway_key_remark=remarks.get(entity.gateway_key_id or ""),
                gateway_has_multiple_keys=gateway_has_multiple_keys,
                channel_has_multiple_credentials=(
                    credential_counts.get(entity.channel_id or "", 0) > 1
                ),
                credential_metadata=credential_metadata,
            )
            for entity in entities
        ]

    @staticmethod
    async def _gateway_has_multiple_keys(session: AsyncSession) -> bool:
        rows = (await session.execute(select(GatewayApiKeyEntity.id).limit(2))).all()
        return len(rows) > 1

    async def _request_log_channel_credentials(
        self, session: AsyncSession, channel_ids: list[str | None]
    ) -> tuple[
        dict[str, int],
        dict[tuple[str, str], tuple[str, int]],
    ]:
        channels_by_protocol_config, protocol_by_channel_id = (
            _channel_ids_by_protocol_config(channel_ids)
        )

        if not channels_by_protocol_config:
            return {}, {}

        protocol_config_ids = list(channels_by_protocol_config.keys())
        protocol_config_rows = (
            await session.execute(
                select(
                    SiteProtocolConfigEntity.id,
                    SiteProtocolConfigEntity.site_id,
                    SiteProtocolConfigEntity.credential_id,
                ).where(SiteProtocolConfigEntity.id.in_(protocol_config_ids))
            )
        ).all()
        channels_by_site: dict[str, list[str]] = {}
        for protocol_config_id, site_id, _ in protocol_config_rows:
            channels_by_site.setdefault(str(site_id), []).extend(
                channels_by_protocol_config.get(str(protocol_config_id), [])
            )

        if not channels_by_site:
            return {}, {}

        model_rows = (
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
        model_credentials_by_config: dict[str, list[tuple[str, str | None]]] = {}
        for protocol_config_id, credential_id, protocol in model_rows:
            if not credential_id:
                continue
            model_credentials_by_config.setdefault(str(protocol_config_id), []).append(
                (
                    str(credential_id),
                    str(protocol) if protocol is not None else None,
                )
            )

        credential_rows = (
            await session.execute(
                select(
                    SiteCredentialEntity.id,
                    SiteCredentialEntity.site_id,
                    SiteCredentialEntity.name,
                )
                .where(SiteCredentialEntity.site_id.in_(list(channels_by_site)))
                .order_by(
                    SiteCredentialEntity.site_id.asc(),
                    SiteCredentialEntity.sort_order.asc(),
                    SiteCredentialEntity.id.asc(),
                )
            )
        ).all()
        credentials_by_site: dict[str, dict[str, tuple[str, int]]] = {}
        credential_numbers_by_site: dict[str, int] = {}
        for credential_id, site_id, credential_name in credential_rows:
            normalized_site_id = str(site_id)
            credential_numbers_by_site[normalized_site_id] = (
                credential_numbers_by_site.get(normalized_site_id, 0) + 1
            )
            credentials_by_site.setdefault(normalized_site_id, {})[
                str(credential_id)
            ] = (
                str(credential_name or ""),
                credential_numbers_by_site[normalized_site_id],
            )

        credential_counts: dict[str, int] = {}
        credential_metadata: dict[tuple[str, str], tuple[str, int]] = {}
        for (
            protocol_config_id,
            site_id,
            default_credential_id,
        ) in protocol_config_rows:
            normalized_site_id = str(site_id)
            site_credentials = credentials_by_site.get(normalized_site_id, {})
            normalized_default_id = (
                str(default_credential_id).strip() if default_credential_id else ""
            )
            for channel_id in channels_by_protocol_config.get(
                str(protocol_config_id), []
            ):
                channel_protocol = protocol_by_channel_id.get(channel_id)
                bound_credential_ids: set[str] = set()
                default_credential = site_credentials.get(normalized_default_id)
                if default_credential is not None:
                    bound_credential_ids.add(normalized_default_id)
                for credential_id, model_protocol in model_credentials_by_config.get(
                    str(protocol_config_id), []
                ):
                    if (
                        channel_protocol is not None
                        and model_protocol != channel_protocol.value
                    ):
                        continue
                    credential = site_credentials.get(credential_id)
                    if credential is not None:
                        bound_credential_ids.add(credential_id)

                credential_counts[channel_id] = len(bound_credential_ids)
                for credential_id, (
                    credential_name,
                    credential_number,
                ) in site_credentials.items():
                    credential_metadata[(channel_id, credential_id)] = (
                        credential_name,
                        credential_number,
                    )

        return credential_counts, credential_metadata
