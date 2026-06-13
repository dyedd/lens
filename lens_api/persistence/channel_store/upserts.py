from __future__ import annotations

from sqlalchemy import update

from ...core.runtime_channel_ids import compose_runtime_channel_id
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


class ChannelUpsertsMixin:
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

    async def _upsert_protocol_configs(
        self,
        session: AsyncSession,
        site_id: str,
        protocol_configs: list[SiteProtocolConfigInput],
        credential_ids: set[str],
        base_url_ids: set[str],
        disabled_base_url_ids: set[str],
    ) -> set[str]:
        protocol_config_ids: set[str] = set()
        protocol_config_keys: set[tuple[str, str]] = set()
        for protocol_config in protocol_configs:
            protocol_config_id = protocol_config.id or str(uuid.uuid4())
            protocol_config_ids.add(protocol_config_id)
            if protocol_config.base_url_id not in base_url_ids:
                raise ValueError(
                    "Base URL not found for protocol config "
                    f"{protocol_config_id}: {protocol_config.base_url_id}"
                )
            if (
                protocol_config.credential_id
                and protocol_config.credential_id not in credential_ids
            ):
                raise ValueError(
                    "Credential not found for protocol config "
                    f"{protocol_config_id}: {protocol_config.credential_id}"
                )
            input_protocols = _deduplicate_protocols(protocol_config.protocols)
            if not input_protocols:
                raise ValueError(
                    "At least one upstream protocol is required for protocol config "
                    f"{protocol_config_id}"
                )
            protocol_config_key = (
                protocol_config.base_url_id,
                protocol_config.credential_id,
            )
            if protocol_config_key in protocol_config_keys:
                raise ValueError(
                    "Duplicate protocol config for "
                    f"base_url_id={protocol_config.base_url_id} "
                    f"credential_id={protocol_config.credential_id}"
                )
            protocol_config_keys.add(protocol_config_key)

            entity = await session.get(SiteProtocolConfigEntity, protocol_config_id)
            if entity is None:
                entity = SiteProtocolConfigEntity(id=protocol_config_id)
                session.add(entity)
            entity.site_id = site_id
            entity.name = protocol_config.name.strip()
            entity.protocols_json = _dump_protocols_json(input_protocols)
            entity.enabled = int(protocol_config.enabled)
            entity.headers_json = json.dumps(protocol_config.headers, ensure_ascii=True)
            entity.proxy_mode = protocol_config.proxy_mode.value
            entity.channel_proxy = protocol_config.channel_proxy
            entity.param_override = protocol_config.param_override
            entity.match_regex = protocol_config.match_regex
            entity.base_url_id = protocol_config.base_url_id
            entity.credential_id = protocol_config.credential_id

            await self._upsert_protocol_config_models(
                session,
                protocol_config_id,
                protocol_config,
                credential_ids,
            )
            if (
                not protocol_config.enabled
                or protocol_config.base_url_id in disabled_base_url_ids
            ):
                await self._disable_group_items_for_channels(
                    session,
                    protocol_config_id,
                    input_protocols,
                )
        return protocol_config_ids

    async def _disable_group_items_for_channels(
        self,
        session: AsyncSession,
        protocol_config_id: str,
        protocols: list[ProtocolKind],
    ) -> None:
        channel_ids = [
            compose_runtime_channel_id(protocol_config_id, protocol)
            for protocol in protocols
        ]
        if not channel_ids:
            return
        await session.execute(
            update(ModelGroupItemEntity)
            .where(ModelGroupItemEntity.channel_id.in_(channel_ids))
            .values(enabled=0)
        )

    async def _upsert_protocol_config_models(
        self,
        session: AsyncSession,
        protocol_config_id: str,
        protocol_config: SiteProtocolConfigInput,
        credential_ids: set[str],
    ) -> None:
        await session.execute(
            delete(SiteDiscoveredModelEntity).where(
                SiteDiscoveredModelEntity.protocol_config_id == protocol_config_id
            )
        )
        seen_models: set[tuple[str, str, str | None]] = set()
        seen_row_ids: set[str] = set()

        for model_index, model in enumerate(
            _deduplicate_protocol_config_models(protocol_config.models)
        ):
            model_name = model.model_name.strip()
            if not model_name:
                raise ValueError(
                    f"Model name is required in protocol config {protocol_config_id}"
                )
            if model.credential_id not in credential_ids:
                raise ValueError(
                    "Model credential not found in protocol config "
                    f"{protocol_config_id}: {model.credential_id}"
                )
            if model.protocol is None:
                raise ValueError(
                    "Model protocol is required in protocol config "
                    f"{protocol_config_id}: {model_name}"
                )
            if model.protocol not in protocol_config.protocols:
                raise ValueError(
                    "Model protocol is not enabled in protocol config "
                    f"{protocol_config_id}: {model.protocol.value}"
                )

            protocol_value = model.protocol.value
            model_key = (model.credential_id, model_name, protocol_value)
            if model_key in seen_models:
                raise ValueError(
                    f"Duplicate model in protocol config {protocol_config_id}: {model_name}"
                )
            seen_models.add(model_key)

            model_id = model.id
            if not model_id or model_id in seen_row_ids:
                model_id = str(uuid.uuid4())
            seen_row_ids.add(model_id)

            session.add(
                SiteDiscoveredModelEntity(
                    id=model_id,
                    protocol_config_id=protocol_config_id,
                    credential_id=model.credential_id,
                    model_name=model_name,
                    enabled=int(model.enabled),
                    sort_order=model_index,
                    protocol=protocol_value,
                )
            )

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
                            ModelGroupItemEntity.channel_id, pid
                        )
                        for pid in protocol_config_ids
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
                            ModelGroupItemEntity.channel_id, pid
                        )
                        for pid in protocol_config_ids
                    ]
                )
            )
            .where(~matching_model)
        )
