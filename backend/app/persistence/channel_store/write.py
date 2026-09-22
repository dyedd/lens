from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    delete,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.protocols import ProtocolKind
from app.models.sites import (
    SiteBaseUrl,
    SiteCreate,
    SiteCredential,
    SiteProtocolConfigInput,
    SiteUpdate,
)
from app.persistence.entities import (
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteCredentialRateEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    SiteProtocolConfigSyncTargetEntity,
)

from .cleanup import SiteConfigurationCleanupMixin
from .endpoint_credentials import credential_ids_for_url
from .mapping import credential_pairs


def _naive_utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _dump_rules(rules: list[object]) -> str:
    return json.dumps(
        [
            rule.model_dump(mode="json") if hasattr(rule, "model_dump") else rule
            for rule in rules
        ],
        ensure_ascii=True,
    )


class SiteProtocolConfigUpsertsMixin:
    async def _upsert_protocol_configs(
        self,
        session: AsyncSession,
        site_id: str,
        protocol_configs: list[SiteProtocolConfigInput],
        credentials: list[SiteCredential],
        base_url_ids: set[str],
    ) -> set[str]:
        protocol_config_ids: set[str] = set()
        seen_base_url_ids: set[str] = set()
        for protocol_config in protocol_configs:
            protocol_config_id = protocol_config.id or str(uuid.uuid4())
            protocol_config_ids.add(protocol_config_id)
            if protocol_config.base_url_id not in base_url_ids:
                raise ValueError(
                    "Base URL not found for protocol config "
                    f"{protocol_config_id}: {protocol_config.base_url_id}"
                )
            if protocol_config.base_url_id in seen_base_url_ids:
                raise ValueError(
                    "Duplicate protocol config for "
                    f"base_url_id={protocol_config.base_url_id}"
                )
            seen_base_url_ids.add(protocol_config.base_url_id)
            selected_credential_ids = set(
                credential_ids_for_url(
                    credential_pairs(credentials), protocol_config.base_url_id
                )
            )
            if not selected_credential_ids:
                raise ValueError(
                    "At least one credential is required for protocol config "
                    f"{protocol_config_id}"
                )

            entity = await session.get(SiteProtocolConfigEntity, protocol_config_id)
            if entity is None:
                entity = SiteProtocolConfigEntity(id=protocol_config_id)
                session.add(entity)
            entity.site_id = site_id
            entity.base_url_id = protocol_config.base_url_id

            await self._upsert_protocol_config_models(
                session,
                protocol_config_id,
                protocol_config,
                selected_credential_ids,
            )
            await self._replace_protocol_config_sync_targets(
                session,
                protocol_config_id,
                protocol_config,
                selected_credential_ids,
            )
        missing_urls = base_url_ids - seen_base_url_ids
        if missing_urls:
            missing_label = ", ".join(sorted(missing_urls))
            raise ValueError(
                f"Each base URL must have exactly one protocol config: {missing_label}"
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
        seen_models: set[tuple[str, str, str]] = set()
        seen_row_ids: set[str] = set()

        for model_index, model in enumerate(protocol_config.models):
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
                    source=model.source.value,
                )
            )

    async def _replace_protocol_config_sync_targets(
        self,
        session: AsyncSession,
        protocol_config_id: str,
        protocol_config: SiteProtocolConfigInput,
        credential_ids: set[str],
    ) -> None:
        await session.execute(
            delete(SiteProtocolConfigSyncTargetEntity).where(
                SiteProtocolConfigSyncTargetEntity.protocol_config_id
                == protocol_config_id
            )
        )
        seen_targets: set[tuple[str, str, ProtocolKind]] = set()
        manual_model_keys = {
            (model.credential_id, model.model_name.strip(), model.protocol)
            for model in protocol_config.models
            if model.source.value == "manual"
        }
        for target in protocol_config.sync_targets:
            if target.credential_id not in credential_ids:
                raise ValueError(
                    "Sync target credential not found in protocol config "
                    f"{protocol_config_id}: {target.credential_id}"
                )
            model_name = target.model_name.strip()
            target_key = (target.credential_id, model_name, target.protocol)
            if not model_name or target_key in seen_targets:
                raise ValueError(
                    f"Duplicate sync target in protocol config {protocol_config_id}: "
                    f"{model_name}"
                )
            seen_targets.add(target_key)
            if target_key in manual_model_keys:
                raise ValueError(
                    "Sync target conflicts with manual model in protocol config "
                    f"{protocol_config_id}: {model_name}"
                )
            session.add(
                SiteProtocolConfigSyncTargetEntity(
                    id=str(uuid.uuid4()),
                    protocol_config_id=protocol_config_id,
                    credential_id=target.credential_id,
                    protocol=target.protocol.value,
                    model_name=model_name,
                )
            )
        synced_model_keys = {
            (model.credential_id, model.model_name.strip(), model.protocol)
            for model in protocol_config.models
            if model.source.value == "synced"
        }
        if missing_targets := synced_model_keys - seen_targets:
            _, model_name, _ = next(iter(missing_targets))
            raise ValueError(
                "Synced model is missing its sync target in protocol config "
                f"{protocol_config_id}: {model_name}"
            )


class SiteConfigUpsertsMixin(
    SiteProtocolConfigUpsertsMixin, SiteConfigurationCleanupMixin
):
    async def _upsert_site_payload(
        self,
        session: AsyncSession,
        site_id: str,
        payload: SiteCreate | SiteUpdate,
        *,
        enabled: bool,
    ) -> None:
        trimmed_name = payload.name.strip()
        if not trimmed_name:
            raise ValueError("Site name is required")
        if not payload.base_urls:
            raise ValueError("At least one base URL is required")

        built_base_urls = self._build_base_urls(payload.base_urls)
        base_url_ids = {item.id for item in built_base_urls}
        built_credentials = self._build_credentials(payload.credentials, base_url_ids)
        previous_credential_ids = set(await self._site_credential_ids(session, site_id))
        now = _naive_utc_now()
        site = await session.get(SiteEntity, site_id)
        if site is None:
            session.add(
                SiteEntity(
                    id=site_id,
                    name=trimmed_name,
                    enabled=int(enabled),
                    tags_json=json.dumps(payload.tags, ensure_ascii=True),
                    updated_at=now,
                    headers_json=_dump_rules(payload.headers),
                    proxy_mode=payload.proxy_mode.value,
                    channel_proxy=payload.channel_proxy.strip(),
                    param_override=_dump_rules(payload.param_override),
                )
            )
        else:
            site.name = trimmed_name
            site.enabled = int(enabled)
            site.tags_json = json.dumps(payload.tags, ensure_ascii=True)
            site.updated_at = now
            site.headers_json = _dump_rules(payload.headers)
            site.proxy_mode = payload.proxy_mode.value
            site.channel_proxy = payload.channel_proxy.strip()
            site.param_override = _dump_rules(payload.param_override)

        await self._upsert_base_urls(session, site_id, built_base_urls)
        current_protocol_config_ids = set(
            await self._site_protocol_config_ids(session, site_id)
        )
        await self._upsert_credentials(session, site_id, built_credentials)
        next_protocol_config_ids = {
            protocol.id for protocol in payload.protocols if protocol.id
        }
        await self._cleanup_deleted_protocol_configs(
            session, current_protocol_config_ids - next_protocol_config_ids
        )
        await self._upsert_protocol_configs(
            session,
            site_id,
            payload.protocols,
            built_credentials,
            base_url_ids,
        )
        await self._upsert_credential_rates(
            session,
            built_credentials,
            payload.protocols,
            previous_credential_ids,
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
                    sort_order=index,
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
                    sort_order=index,
                    base_url_id=item.base_url_id,
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
            bound_ids = set(
                credential_ids_for_url(
                    credential_pairs(credentials), protocol.base_url_id
                )
            )
            if credential.id not in bound_ids:
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


async def update_rate(
    session_factory: async_sessionmaker[AsyncSession],
    credential_id: str,
    *,
    protocol_config_id: str,
    source: str,
    group_name: str,
    **values: object,
) -> bool:
    async with session_factory() as session:
        result = await session.execute(
            update(SiteCredentialRateEntity)
            .where(
                SiteCredentialRateEntity.credential_id == credential_id,
                SiteCredentialRateEntity.protocol_config_id == protocol_config_id,
                SiteCredentialRateEntity.source == source,
                SiteCredentialRateEntity.group_name == group_name,
            )
            .values(**values)
        )
        await session.commit()
        return result.rowcount == 1


class SiteCredentialRateRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record_success(
        self,
        credential_id: str,
        *,
        multiplier: float,
        observed_at: str,
        synced_at: str,
        protocol_config_id: str,
        source: str,
        group_name: str,
    ) -> bool:
        return await update_rate(
            self._session_factory,
            credential_id,
            protocol_config_id=protocol_config_id,
            source=source,
            group_name=group_name,
            multiplier=multiplier,
            observed_at=observed_at,
            last_synced_at=synced_at,
            last_error="",
        )

    async def record_failure(
        self,
        credential_id: str,
        error: str,
        *,
        protocol_config_id: str,
        source: str,
        group_name: str,
    ) -> bool:
        return await update_rate(
            self._session_factory,
            credential_id,
            protocol_config_id=protocol_config_id,
            source=source,
            group_name=group_name,
            last_error=error[:2000],
        )
