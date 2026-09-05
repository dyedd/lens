from __future__ import annotations

import uuid

from sqlalchemy import (
    delete,
    select,
)

from app.core.errors import ResourceNotFoundError
from app.models.protocols import ModelSource, ProtocolKind
from app.models.site_model_test import SiteModelFetchRequest
from app.models.sites import SiteCredential
from app.persistence.entities import (
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteCredentialRateEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigCredentialEntity,
    SiteProtocolConfigEntity,
)
from app.persistence.protocol_serialization import parse_supported_protocols


class ChannelSiteOperationsMixin:
    async def delete_site(self, site_id: str) -> None:
        """Delete a site and its dependent channel data."""
        async with self._session_factory() as session:
            site = await session.get(SiteEntity, site_id)
            if site is None:
                raise ResourceNotFoundError(site_id)

            protocol_config_ids = await self._site_protocol_config_ids(session, site_id)
            credential_ids = await self._site_credential_ids(session, site_id)
            await self._cleanup_deleted_protocol_configs(
                session, set(protocol_config_ids)
            )
            if credential_ids:
                await session.execute(
                    delete(SiteCredentialRateEntity).where(
                        SiteCredentialRateEntity.credential_id.in_(credential_ids)
                    )
                )
                await session.execute(
                    delete(SiteCredentialEntity).where(
                        SiteCredentialEntity.id.in_(credential_ids)
                    )
                )
            await session.execute(
                delete(SiteBaseUrlEntity).where(SiteBaseUrlEntity.site_id == site_id)
            )
            await session.delete(site)
            await self._cleanup_invalid_group_items(session, set(protocol_config_ids))
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

    async def replace_protocol_config_synced_models(
        self,
        protocol_config_id: str,
        credential_id: str,
        protocol: ProtocolKind,
        model_names: list[str],
    ) -> None:
        """Replace one credential/protocol target's synchronized models."""
        async with self._session_factory() as session:
            entity = await session.get(SiteProtocolConfigEntity, protocol_config_id)
            if entity is None:
                raise ResourceNotFoundError(protocol_config_id)
            association = (
                await session.execute(
                    select(SiteProtocolConfigCredentialEntity.id).where(
                        SiteProtocolConfigCredentialEntity.protocol_config_id
                        == protocol_config_id,
                        SiteProtocolConfigCredentialEntity.credential_id
                        == credential_id,
                    )
                )
            ).scalar_one_or_none()
            if association is None:
                raise ValueError(
                    "Credential is not bound to protocol config "
                    f"{protocol_config_id}: {credential_id}"
                )

            protocols = parse_supported_protocols(entity.protocols_json)
            if protocol not in protocols:
                raise ValueError(
                    "Protocol is not enabled in protocol config "
                    f"{protocol_config_id}: {protocol.value}"
                )

            target_rows = (
                (
                    await session.execute(
                        select(SiteDiscoveredModelEntity).where(
                            SiteDiscoveredModelEntity.protocol_config_id
                            == protocol_config_id,
                            SiteDiscoveredModelEntity.credential_id == credential_id,
                            SiteDiscoveredModelEntity.protocol == protocol.value,
                        )
                    )
                )
                .scalars()
                .all()
            )
            manual_names = {
                row.model_name
                for row in target_rows
                if row.source == ModelSource.MANUAL.value
            }
            synced_by_name = {
                row.model_name: row
                for row in target_rows
                if row.source == ModelSource.SYNCED.value
            }
            desired_names = set(model_names) - manual_names
            stale_ids = [
                row.id
                for name, row in synced_by_name.items()
                if name not in desired_names
            ]
            if stale_ids:
                await session.execute(
                    delete(SiteDiscoveredModelEntity).where(
                        SiteDiscoveredModelEntity.id.in_(stale_ids)
                    )
                )

            all_rows = (
                (
                    await session.execute(
                        select(SiteDiscoveredModelEntity).where(
                            SiteDiscoveredModelEntity.protocol_config_id
                            == protocol_config_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            next_sort_order = max((row.sort_order for row in all_rows), default=-1) + 1
            for model_name in sorted(desired_names - set(synced_by_name)):
                session.add(
                    SiteDiscoveredModelEntity(
                        id=str(uuid.uuid4()),
                        protocol_config_id=protocol_config_id,
                        credential_id=credential_id,
                        model_name=model_name,
                        enabled=1,
                        sort_order=next_sort_order,
                        protocol=protocol.value,
                        source=ModelSource.SYNCED.value,
                    )
                )
                next_sort_order += 1

            await self._cleanup_invalid_group_items(session, {protocol_config_id})
            await session.commit()
