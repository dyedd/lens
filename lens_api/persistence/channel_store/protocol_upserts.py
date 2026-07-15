from __future__ import annotations

from .shared import (
    AsyncSession,
    ProtocolKind,
    SiteDiscoveredModelEntity,
    SiteProtocolConfigEntity,
    SiteProtocolConfigInput,
    _deduplicate_protocol_config_models,
    _deduplicate_protocols,
    _dump_protocols_json,
    delete,
    json,
    uuid,
)


class ChannelProtocolUpsertsMixin:
    async def _upsert_protocol_configs(
        self,
        session: AsyncSession,
        site_id: str,
        protocol_configs: list[SiteProtocolConfigInput],
        credential_ids: set[str],
        base_url_ids: set[str],
    ) -> set[str]:
        protocol_config_ids: set[str] = set()
        protocol_config_keys: set[tuple[str, str, ProtocolKind]] = set()
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
            for protocol in input_protocols:
                protocol_config_key = (
                    protocol_config.base_url_id,
                    protocol_config.credential_id,
                    protocol,
                )
                if protocol_config_key in protocol_config_keys:
                    raise ValueError(
                        "Duplicate protocol config for "
                        f"base_url_id={protocol_config.base_url_id} "
                        f"credential_id={protocol_config.credential_id} "
                        f"protocol={protocol.value}"
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
            entity.auto_sync_enabled = int(protocol_config.auto_sync_enabled)

            await self._upsert_protocol_config_models(
                session,
                protocol_config_id,
                protocol_config,
                credential_ids,
            )
        return protocol_config_ids

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
