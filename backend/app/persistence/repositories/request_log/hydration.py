from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request_logs import RequestLogItem
from app.persistence.entities import (
    GatewayApiKeyEntity,
    RequestLogEntity,
    SiteCredentialEntity,
    SiteProtocolConfigCredentialEntity,
    SiteProtocolConfigEntity,
)
from app.persistence.repositories.request_log_channel_ids import (
    group_channel_ids_by_protocol_config,
)

from .dto_mapping import to_request_log
from .ports import GatewayKeyPort


class RequestLogHydrator:
    def __init__(self, gateway_key_repo: GatewayKeyPort) -> None:
        self.gateway_key_repo = gateway_key_repo

    async def hydrate_request_logs(
        self,
        session: AsyncSession,
        entities: list[RequestLogEntity],
        *,
        gateway_has_multiple_keys: bool | None = None,
    ) -> list[RequestLogItem]:
        remarks = await self.gateway_key_repo.remarks_by_id(
            session, [entity.gateway_key_id for entity in entities]
        )
        if gateway_has_multiple_keys is None:
            gateway_has_multiple_keys = (
                await self.gateway_has_multiple_keys(session) if entities else False
            )
        (
            credential_counts,
            credential_metadata,
        ) = await self.request_log_channel_credentials(
            session, [entity.channel_id for entity in entities]
        )
        return [
            to_request_log(
                entity,
                gateway_key_remark=remarks.get(entity.gateway_key_id or ""),
                gateway_has_multiple_keys=gateway_has_multiple_keys,
                channel_has_multiple_credentials=credential_counts.get(
                    entity.channel_id or "", 0
                )
                > 1,
                credential_metadata=credential_metadata,
            )
            for entity in entities
        ]

    @staticmethod
    async def gateway_has_multiple_keys(session: AsyncSession) -> bool:
        rows = (await session.execute(select(GatewayApiKeyEntity.id).limit(2))).all()
        return len(rows) > 1

    async def request_log_channel_credentials(
        self, session: AsyncSession, channel_ids: list[str | None]
    ) -> tuple[dict[str, int], dict[tuple[str, str], tuple[str, int]]]:
        channels_by_protocol_config, _ = group_channel_ids_by_protocol_config(
            channel_ids
        )
        if not channels_by_protocol_config:
            return ({}, {})
        protocol_config_ids = list(channels_by_protocol_config.keys())
        protocol_config_rows = (
            await session.execute(
                select(
                    SiteProtocolConfigEntity.id, SiteProtocolConfigEntity.site_id
                ).where(SiteProtocolConfigEntity.id.in_(protocol_config_ids))
            )
        ).all()
        channels_by_site: dict[str, list[str]] = {}
        for protocol_config_id, site_id in protocol_config_rows:
            channels_by_site.setdefault(str(site_id), []).extend(
                channels_by_protocol_config.get(str(protocol_config_id), [])
            )
        if not channels_by_site:
            return ({}, {})
        protocol_credential_rows = (
            await session.execute(
                select(
                    SiteProtocolConfigCredentialEntity.protocol_config_id,
                    SiteProtocolConfigCredentialEntity.credential_id,
                ).where(
                    SiteProtocolConfigCredentialEntity.protocol_config_id.in_(
                        protocol_config_ids
                    )
                )
            )
        ).all()
        credential_ids_by_config: dict[str, set[str]] = {}
        for protocol_config_id, credential_id in protocol_credential_rows:
            credential_ids_by_config.setdefault(str(protocol_config_id), set()).add(
                str(credential_id)
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
            site_id_text = str(site_id)
            credential_numbers_by_site[site_id_text] = (
                credential_numbers_by_site.get(site_id_text, 0) + 1
            )
            credentials_by_site.setdefault(site_id_text, {})[str(credential_id)] = (
                str(credential_name or ""),
                credential_numbers_by_site[site_id_text],
            )
        credential_counts: dict[str, int] = {}
        credential_metadata: dict[tuple[str, str], tuple[str, int]] = {}
        for protocol_config_id, site_id in protocol_config_rows:
            site_id_text = str(site_id)
            site_credentials = credentials_by_site.get(site_id_text, {})
            for channel_id in channels_by_protocol_config.get(
                str(protocol_config_id), []
            ):
                bound_credential_ids = {
                    credential_id
                    for credential_id in credential_ids_by_config.get(
                        str(protocol_config_id), set()
                    )
                    if credential_id in site_credentials
                }
                credential_counts[channel_id] = len(bound_credential_ids)
                for credential_id, (
                    credential_name,
                    credential_number,
                ) in site_credentials.items():
                    credential_metadata[channel_id, credential_id] = (
                        credential_name,
                        credential_number,
                    )
        return (credential_counts, credential_metadata)
