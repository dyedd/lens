from __future__ import annotations

from .shared import (
    ModelGroupItemEntity,
    ProtocolKind,
    SiteBaseUrlEntity,
    SiteCredential,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteModelFetchRequest,
    SiteModelInput,
    SiteProtocolConfigEntity,
    SiteProtocolConfigInput,
    _channel_id_matches_protocol_config,
    delete,
    or_,
    select,
    uuid,
)
from ..shared import _parse_supported_protocols_json


class ChannelSiteOperationsMixin:
    async def delete_site(self, site_id: str) -> None:
        """Delete a site and its dependent channel data."""
        async with self._session_factory() as session:
            site = await session.get(SiteEntity, site_id)
            if site is None:
                raise KeyError(site_id)

            protocol_config_ids = await self._site_protocol_config_ids(session, site_id)
            credential_ids = await self._site_credential_ids(session, site_id)
            if protocol_config_ids:
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
                        SiteDiscoveredModelEntity.protocol_config_id.in_(
                            protocol_config_ids
                        )
                    )
                )
                await session.execute(
                    delete(SiteProtocolConfigEntity).where(
                        SiteProtocolConfigEntity.id.in_(protocol_config_ids)
                    )
                )
            if credential_ids:
                await session.execute(
                    delete(SiteCredentialEntity).where(
                        SiteCredentialEntity.id.in_(credential_ids)
                    )
                )
            await session.execute(
                delete(SiteBaseUrlEntity).where(SiteBaseUrlEntity.site_id == site_id)
            )
            await session.delete(site)
            await session.commit()

    async def fetch_models_preview(
        self, payload: SiteModelFetchRequest
    ) -> list[dict[str, str]]:
        """Validate model discovery credentials and return preview entries."""
        credentials = [
            SiteCredential(
                id=item.id or str(uuid.uuid4()),
                name=item.name.strip(),
                api_key=item.api_key,
                enabled=item.enabled,
                sort_order=index,
            )
            for index, item in enumerate(payload.credentials)
            if item.name.strip() and item.api_key.strip()
        ]
        credential_map = {item.id: item for item in credentials}
        credential_ids = list(dict.fromkeys(payload.credential_ids))
        if not credential_ids:
            raise ValueError("At least one credential is required for model discovery")

        previews: list[dict[str, str]] = []
        for credential_id in credential_ids:
            credential = credential_map.get(credential_id)
            if credential is None:
                raise ValueError(
                    f"Credential not found for model discovery: {credential_id}"
                )
            if not credential.enabled:
                raise ValueError(
                    f"Credential is disabled for model discovery: {credential_id}"
                )
            previews.append(
                {
                    "credential_id": credential.id,
                    "credential_name": credential.name,
                }
            )
        return previews

    async def replace_protocol_config_models(
        self,
        protocol_config_id: str,
        model_names_by_protocol: dict[ProtocolKind, list[str]],
    ) -> None:
        """Replace discovered models for a protocol configuration."""
        async with self._session_factory() as session:
            entity = await session.get(SiteProtocolConfigEntity, protocol_config_id)
            if entity is None:
                raise KeyError(protocol_config_id)
            credential_id = entity.credential_id
            if not credential_id:
                raise ValueError(
                    f"Protocol config has no bound credential: {protocol_config_id}"
                )

            protocols = _parse_supported_protocols_json(entity.protocols_json)
            existing_enabled = {
                (row.model_name, row.protocol): bool(row.enabled)
                for row in (
                    await session.execute(
                        select(SiteDiscoveredModelEntity).where(
                            SiteDiscoveredModelEntity.protocol_config_id
                            == protocol_config_id
                        )
                    )
                )
                .scalars()
                .all()
            }
            models = [
                SiteModelInput(
                    credential_id=credential_id,
                    model_name=model_name,
                    enabled=existing_enabled.get((model_name, protocol.value), True),
                    protocol=protocol,
                )
                for protocol in protocols
                for model_name in model_names_by_protocol.get(protocol, [])
            ]
            protocol_config = SiteProtocolConfigInput(
                id=protocol_config_id,
                protocols=protocols,
                base_url_id=entity.base_url_id,
                credential_id=credential_id,
                models=models,
            )

            await self._upsert_protocol_config_models(
                session,
                protocol_config_id,
                protocol_config,
                {credential_id},
            )
            await self._cleanup_invalid_group_items(session, {protocol_config_id})
            await session.commit()
