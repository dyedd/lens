from __future__ import annotations

import json

from .cleanup import ChannelCleanupMixin
from .protocol_upserts import ChannelProtocolUpsertsMixin
from .shared import (
    AsyncSession,
    SiteBaseUrl,
    SiteBaseUrlEntity,
    SiteBaseUrlInput,
    SiteCredential,
    SiteCredentialEntity,
    SiteCredentialRateEntity,
    SiteCredentialInput,
    SiteEntity,
    SiteProtocolConfigInput,
    _dump_protocols_json,
    delete,
    select,
)


class ChannelUpsertsMixin(ChannelProtocolUpsertsMixin, ChannelCleanupMixin):
    async def _upsert_site_payload(
        self,
        session: AsyncSession,
        site_id: str,
        name: str,
        enabled: bool,
        tags: list[str],
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
        previous_credential_ids = set(await self._site_credential_ids(session, site_id))
        credential_ids = {item.id for item in normalized_credentials}
        base_url_ids = {item.id for item in normalized_base_urls}

        site = await session.get(SiteEntity, site_id)
        if site is None:
            session.add(
                SiteEntity(
                    id=site_id,
                    name=normalized_name,
                    enabled=int(enabled),
                    tags_json=json.dumps(tags, ensure_ascii=True),
                )
            )
        else:
            site.name = normalized_name
            site.enabled = int(enabled)
            site.tags_json = json.dumps(tags, ensure_ascii=True)

        await self._upsert_base_urls(session, site_id, normalized_base_urls)
        current_protocol_config_ids = set(
            await self._site_protocol_config_ids(session, site_id)
        )
        await self._upsert_credentials(session, site_id, normalized_credentials)

        next_protocol_config_ids = await self._upsert_protocol_configs(
            session,
            site_id,
            protocols,
            credential_ids,
            base_url_ids,
        )
        await self._upsert_credential_rates(
            session,
            normalized_credentials,
            protocols,
            previous_credential_ids,
        )

        await self._cleanup_deleted_protocol_configs(
            session, current_protocol_config_ids - next_protocol_config_ids
        )
        await self._cleanup_invalid_group_items(
            session, current_protocol_config_ids | next_protocol_config_ids
        )

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

    async def _upsert_credential_rates(
        self,
        session: AsyncSession,
        credentials: list[SiteCredential],
        protocols: list[SiteProtocolConfigInput],
        previous_credential_ids: set[str],
    ) -> None:
        protocol_by_id = {item.id: item for item in protocols if item.id}
        next_credential_ids = {item.id for item in credentials}
        stale_credential_ids = previous_credential_ids - next_credential_ids
        if stale_credential_ids:
            await session.execute(
                delete(SiteCredentialRateEntity).where(
                    SiteCredentialRateEntity.credential_id.in_(stale_credential_ids)
                )
            )

        rate_rows = (
            (
                await session.execute(
                    select(SiteCredentialRateEntity).where(
                        SiteCredentialRateEntity.credential_id.in_(next_credential_ids)
                    )
                )
            )
            .scalars()
            .all()
            if next_credential_ids
            else []
        )
        rates_by_credential = {row.credential_id: row for row in rate_rows}
        for credential in credentials:
            entity = rates_by_credential.get(credential.id)
            if credential.rate_source == "none":
                if entity is not None:
                    await session.delete(entity)
                continue

            protocol = protocol_by_id.get(credential.rate_protocol_config_id)
            if protocol is None:
                raise ValueError(
                    "Rate protocol config not found for credential "
                    f"{credential.id}: {credential.rate_protocol_config_id}"
                )
            if credential.id not in protocol.credential_ids:
                raise ValueError(
                    "Rate credential is not bound to protocol config "
                    f"{credential.rate_protocol_config_id}: {credential.id}"
                )

            if entity is None:
                entity = SiteCredentialRateEntity(credential_id=credential.id)
                session.add(entity)
                config_changed = True
            else:
                config_changed = (
                    entity.protocol_config_id != credential.rate_protocol_config_id
                    or entity.source != credential.rate_source
                    or entity.group_name != credential.rate_group
                )
            entity.protocol_config_id = credential.rate_protocol_config_id
            entity.source = credential.rate_source
            entity.group_name = credential.rate_group
            if config_changed:
                entity.multiplier = None
                entity.observed_at = None
                entity.last_synced_at = None
                entity.last_error = ""
