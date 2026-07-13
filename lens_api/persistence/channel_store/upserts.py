from __future__ import annotations

from sqlalchemy import update

from ...core.runtime_channel_ids import compose_runtime_channel_id
from .cleanup import ChannelCleanupMixin
from .protocol_upserts import ChannelProtocolUpsertsMixin
from .shared import (
    AsyncSession,
    ModelGroupItemEntity,
    ProtocolKind,
    SiteBaseUrl,
    SiteBaseUrlEntity,
    SiteBaseUrlInput,
    SiteCredential,
    SiteCredentialEntity,
    SiteCredentialInput,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    SiteProtocolConfigInput,
    _channel_id_matches_protocol_config,
    _deduplicate_protocols,
    _deduplicate_protocol_config_models,
    _dump_protocols_json,
    delete,
    json,
    or_,
    select,
    uuid,
)


class ChannelUpsertsMixin(ChannelProtocolUpsertsMixin, ChannelCleanupMixin):
    async def _upsert_site_payload(
        self,
        session: AsyncSession,
        site_id: str,
        name: str,
        base_urls: list[SiteBaseUrlInput],
        credentials: list[SiteCredentialInput],
        protocols: list[SiteProtocolConfigInput],
    ) -> None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Site name is required")
        if not base_urls:
            raise ValueError("At least one base URL is required")

        normalized_base_urls = self._normalize_base_urls(base_urls)
        normalized_credentials = self._normalize_credentials(credentials)
        credential_ids = {item.id for item in normalized_credentials}
        base_url_ids = {item.id for item in normalized_base_urls}
        disabled_base_url_ids = {
            item.id for item in normalized_base_urls if not item.enabled
        }
        disabled_credential_ids = {
            item.id for item in normalized_credentials if not item.enabled
        }

        site = await session.get(SiteEntity, site_id)
        if site is None:
            session.add(SiteEntity(id=site_id, name=normalized_name))
        else:
            site.name = normalized_name

        await self._upsert_base_urls(session, site_id, normalized_base_urls)
        current_protocol_config_ids = set(
            await self._site_protocol_config_ids(session, site_id)
        )
        current_credential_ids = set(await self._site_credential_ids(session, site_id))
        await self._upsert_credentials(session, site_id, normalized_credentials)

        next_protocol_config_ids = await self._upsert_protocol_configs(
            session,
            site_id,
            protocols,
            credential_ids,
            base_url_ids,
            disabled_base_url_ids,
            disabled_credential_ids,
        )

        await self._cleanup_deleted_protocol_configs(
            session, current_protocol_config_ids - next_protocol_config_ids
        )
        await self._cleanup_deleted_credentials(
            session, current_credential_ids - credential_ids
        )
        await self._cleanup_invalid_group_items(session, next_protocol_config_ids)

    async def _upsert_base_urls(
        self, session: AsyncSession, site_id: str, items: list[SiteBaseUrl]
    ) -> None:
        await session.execute(
            delete(SiteBaseUrlEntity).where(SiteBaseUrlEntity.site_id == site_id)
        )
        for index, item in enumerate(items):
            session.add(
                SiteBaseUrlEntity(
                    id=item.id,
                    site_id=site_id,
                    url=str(item.url),
                    name=item.name,
                    enabled=int(item.enabled),
                    sort_order=index,
                    supported_protocols_json=_dump_protocols_json(
                        item.supported_protocols
                    ),
                )
            )

    async def _upsert_credentials(
        self, session: AsyncSession, site_id: str, items: list[SiteCredential]
    ) -> None:
        await session.execute(
            delete(SiteCredentialEntity).where(SiteCredentialEntity.site_id == site_id)
        )
        for index, item in enumerate(items):
            session.add(
                SiteCredentialEntity(
                    id=item.id,
                    site_id=site_id,
                    name=item.name,
                    api_key=item.api_key,
                    enabled=int(item.enabled),
                    sort_order=index,
                )
            )
