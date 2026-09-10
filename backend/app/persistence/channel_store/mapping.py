from __future__ import annotations

import json
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channels import ChannelConfig, ChannelDiscoveredModel, ChannelKeyItem
from app.models.protocols import ChannelStatus, ProtocolKind
from app.models.sites import (
    SiteBaseUrl,
    SiteBaseUrlInput,
    SiteConfig,
    SiteCredential,
    SiteCredentialInput,
    SiteModel,
    SiteProtocolConfig,
    SiteSyncTarget,
)
from app.models.upstream_rules import HeaderRule, ParamOverrideRule
from app.persistence.entities import (
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteCredentialRateEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    SiteProtocolConfigSyncTargetEntity,
)
from app.persistence.protocol_serialization import parse_supported_protocols

from ...core.runtime_channel_ids import compose_runtime_channel_id
from ..site_loader import fetch_site_rows


class ChannelRowMappingMixin:
    def _group_base_urls(
        self, rows: list[SiteBaseUrlEntity]
    ) -> dict[str, list[SiteBaseUrl]]:
        result: dict[str, list[SiteBaseUrl]] = defaultdict(list)
        for row in rows:
            result[row.site_id].append(
                SiteBaseUrl(
                    id=row.id,
                    url=row.url,
                    name=row.name,
                    enabled=bool(row.enabled),
                    sort_order=row.sort_order,
                    supported_protocols=parse_supported_protocols(
                        row.supported_protocols_json
                    ),
                )
            )
        return result

    def _group_credentials(
        self,
        rows: list[SiteCredentialEntity],
        rate_rows: list[SiteCredentialRateEntity],
    ) -> tuple[dict[str, list[SiteCredential]], dict[str, SiteCredential]]:
        by_site: dict[str, list[SiteCredential]] = defaultdict(list)
        by_id: dict[str, SiteCredential] = {}
        rates_by_credential = {row.credential_id: row for row in rate_rows}
        for row in rows:
            rate = rates_by_credential.get(row.id)
            item = SiteCredential(
                id=row.id,
                name=row.name,
                api_key=row.api_key,
                enabled=bool(row.enabled),
                sort_order=row.sort_order,
                rate_source=rate.source if rate is not None else "none",
                rate_protocol_config_id=(
                    rate.protocol_config_id if rate is not None else ""
                ),
                rate_group=rate.group_name if rate is not None else "",
                rate_multiplier=rate.multiplier if rate is not None else None,
                rate_observed_at=rate.observed_at if rate is not None else None,
                rate_last_synced_at=(rate.last_synced_at if rate is not None else None),
                rate_last_error=rate.last_error if rate is not None else "",
            )
            by_site[row.site_id].append(item)
            by_id[row.id] = item
        return by_site, by_id

    def _group_models(
        self,
        rows: list[SiteDiscoveredModelEntity],
        credentials_by_id: dict[str, SiteCredential],
    ) -> dict[str, list[SiteModel]]:
        result: dict[str, list[SiteModel]] = defaultdict(list)
        valid_protocol_values = {protocol_kind.value for protocol_kind in ProtocolKind}
        for row in rows:
            credential = credentials_by_id.get(row.credential_id)
            result[row.protocol_config_id].append(
                SiteModel(
                    id=row.id,
                    credential_id=row.credential_id,
                    credential_name=credential.name if credential else "",
                    model_name=row.model_name,
                    enabled=bool(row.enabled),
                    sort_order=row.sort_order,
                    protocol=(
                        ProtocolKind(row.protocol)
                        if row.protocol in valid_protocol_values
                        else None
                    ),
                    source=row.source,
                )
            )
        return result

    def _group_sync_targets(
        self, rows: list[SiteProtocolConfigSyncTargetEntity]
    ) -> dict[str, list[SiteSyncTarget]]:
        result: dict[str, list[SiteSyncTarget]] = defaultdict(list)
        valid_protocol_values = {protocol_kind.value for protocol_kind in ProtocolKind}
        for row in rows:
            if row.protocol not in valid_protocol_values:
                continue
            result[row.protocol_config_id].append(
                SiteSyncTarget(
                    credential_id=row.credential_id,
                    model_name=row.model_name,
                    protocol=ProtocolKind(row.protocol),
                )
            )
        return result

    def _group_protocols(
        self,
        rows: list[SiteProtocolConfigEntity],
        models_by_protocol_config: dict[str, list[SiteModel]],
        sync_targets_by_protocol_config: dict[str, list[SiteSyncTarget]],
        credential_ids_by_protocol_config: dict[str, list[str]],
    ) -> dict[str, list[SiteProtocolConfig]]:
        result: dict[str, list[SiteProtocolConfig]] = defaultdict(list)
        for row in rows:
            result[row.site_id].append(
                SiteProtocolConfig(
                    id=row.id,
                    name=row.name,
                    protocols=parse_supported_protocols(row.protocols_json),
                    enabled=bool(row.enabled),
                    headers=[
                        HeaderRule.model_validate(item)
                        for item in json.loads(row.headers_json)
                    ],
                    proxy_mode=row.proxy_mode,
                    channel_proxy=row.channel_proxy,
                    param_override=[
                        ParamOverrideRule.model_validate(item)
                        for item in json.loads(row.param_override)
                    ],
                    base_url_id=row.base_url_id,
                    credential_ids=credential_ids_by_protocol_config.get(row.id, []),
                    sync_targets=sync_targets_by_protocol_config.get(row.id, []),
                    models=models_by_protocol_config.get(row.id, []),
                )
            )
        return result


class SiteChannelProjectionMixin(ChannelRowMappingMixin):
    def flatten_site(self, site: SiteConfig) -> list[ChannelConfig]:
        credentials_by_id = {item.id: item for item in site.credentials}
        base_urls_by_id = {item.id: item for item in site.base_urls}
        items: list[ChannelConfig] = []
        for protocol_config in site.protocols:
            bound_base_url = base_urls_by_id.get(protocol_config.base_url_id)
            if bound_base_url is None:
                raise ValueError(
                    "Base URL not found for protocol config "
                    f"{protocol_config.id}: {protocol_config.base_url_id}"
                )
            protocols = protocol_config.protocols
            if not protocols:
                continue
            keys = self._build_channel_keys(protocol_config, credentials_by_id)
            if not keys:
                continue
            active_key = next((k for k in keys if k.enabled), keys[0])
            models_by_protocol = self._models_by_protocol(protocol_config.models)
            for protocol in protocols:
                protocol_models = models_by_protocol.get(protocol, [])
                items.append(
                    ChannelConfig(
                        id=compose_runtime_channel_id(protocol_config.id, protocol),
                        site_id=site.id,
                        name=site.name,
                        protocol=protocol,
                        base_url=bound_base_url.url,
                        api_key=active_key.key,
                        status=(
                            ChannelStatus.ENABLED
                            if site.enabled
                            and protocol_config.enabled
                            and bound_base_url.enabled
                            else ChannelStatus.DISABLED
                        ),
                        headers=protocol_config.headers,
                        model_patterns=[
                            m.model_name for m in protocol_models if m.enabled
                        ],
                        keys=keys,
                        models=self._build_channel_models(
                            protocol_models, credentials_by_id
                        ),
                        proxy_mode=protocol_config.proxy_mode,
                        channel_proxy=protocol_config.channel_proxy,
                        param_override=protocol_config.param_override,
                    )
                )
        return items

    def _models_by_protocol(
        self, models: list[SiteModel]
    ) -> dict[ProtocolKind, list[SiteModel]]:
        result: dict[ProtocolKind, list[SiteModel]] = defaultdict(list)
        for model in models:
            if model.protocol is not None:
                result[model.protocol].append(model)
        return result

    def _build_channel_keys(
        self,
        protocol_config: SiteProtocolConfig,
        credentials_by_id: dict[str, SiteCredential],
    ) -> list[ChannelKeyItem]:
        credential_numbers = {
            credential_id: index + 1
            for index, credential_id in enumerate(credentials_by_id)
        }
        credential_ids = list(
            dict.fromkeys(
                protocol_config.credential_ids
                + [item.credential_id for item in protocol_config.models]
            )
        )
        return [
            ChannelKeyItem(
                id=credential.id,
                key=credential.api_key,
                remark=credential.name,
                number=credential_numbers[credential.id],
                enabled=credential.enabled,
                rate_source=credential.rate_source,
                rate_multiplier=credential.rate_multiplier,
            )
            for credential_id in credential_ids
            if credential_id and (credential := credentials_by_id.get(credential_id))
        ]

    def _build_channel_models(
        self,
        models: list[SiteModel],
        credentials_by_id: dict[str, SiteCredential],
    ) -> list[ChannelDiscoveredModel]:
        items: list[ChannelDiscoveredModel] = []
        for model in models:
            credential = credentials_by_id.get(model.credential_id)
            items.append(
                ChannelDiscoveredModel(
                    id=model.id,
                    credential_id=model.credential_id,
                    credential_name=(
                        model.credential_name
                        or (credential.name if credential is not None else "")
                    ),
                    model_name=model.model_name,
                    enabled=model.enabled,
                    sort_order=model.sort_order,
                )
            )
        return items

    def _build_credentials(
        self, items: list[SiteCredentialInput]
    ) -> list[SiteCredential]:
        built_credentials: list[SiteCredential] = []
        seen_names: set[str] = set()
        for index, item in enumerate(items):
            name = item.name.strip()
            if not name:
                raise ValueError("Credential name is required")
            name_key = name.lower()
            if name_key in seen_names:
                raise ValueError(f"Duplicate credential name: {name}")
            seen_names.add(name_key)
            built_credentials.append(
                SiteCredential(
                    id=item.id or str(uuid.uuid4()),
                    name=name,
                    api_key=item.api_key,
                    enabled=item.enabled,
                    sort_order=index,
                    rate_source=item.rate_source,
                    rate_protocol_config_id=item.rate_protocol_config_id,
                    rate_group=item.rate_group,
                )
            )
        if not built_credentials:
            raise ValueError("At least one credential is required")
        return built_credentials

    def _build_base_urls(self, items: list[SiteBaseUrlInput]) -> list[SiteBaseUrl]:
        built_base_urls: list[SiteBaseUrl] = []
        for index, item in enumerate(items):
            url_str = str(item.url).strip()
            if not url_str:
                raise ValueError("Base URL is required")
            built_base_urls.append(
                SiteBaseUrl(
                    id=item.id or str(uuid.uuid4()),
                    url=item.url,
                    name=item.name.strip(),
                    enabled=item.enabled,
                    sort_order=index,
                    supported_protocols=list(dict.fromkeys(item.supported_protocols)),
                )
            )
        return built_base_urls

    async def _ensure_site_name_unique(
        self, session: AsyncSession, name: str, exclude_site_id: str | None = None
    ) -> None:
        trimmed_name = name.strip()
        result = await session.execute(
            select(SiteEntity).where(SiteEntity.name == trimmed_name).limit(1)
        )
        row = result.scalar_one_or_none()
        if row is not None and row.id != exclude_site_id:
            raise ValueError(f"Site already exists: {trimmed_name}")

    async def _site_protocol_config_ids(
        self, session: AsyncSession, site_id: str
    ) -> list[str]:
        return list(
            (
                await session.execute(
                    select(SiteProtocolConfigEntity.id).where(
                        SiteProtocolConfigEntity.site_id == site_id
                    )
                )
            )
            .scalars()
            .all()
        )

    async def _site_credential_ids(
        self, session: AsyncSession, site_id: str
    ) -> list[str]:
        return list(
            (
                await session.execute(
                    select(SiteCredentialEntity.id).where(
                        SiteCredentialEntity.site_id == site_id
                    )
                )
            )
            .scalars()
            .all()
        )


class SiteConfigLoadersMixin:
    async def _load_sites(
        self, session: AsyncSession, site_ids: list[str] | None = None
    ) -> list[SiteConfig]:
        rows = await fetch_site_rows(session, site_ids=site_ids)
        if not rows.sites:
            return []

        base_urls_by_site = self._group_base_urls(rows.base_urls)
        credentials_by_site, credentials_by_id = self._group_credentials(
            rows.credentials, rows.credential_rates
        )
        models_by_protocol_config = self._group_models(
            rows.discovered_models, credentials_by_id
        )
        sync_targets_by_protocol_config = self._group_sync_targets(rows.sync_targets)
        credential_ids_by_protocol_config: dict[str, list[str]] = defaultdict(list)
        for row in rows.protocol_credentials:
            credential_ids_by_protocol_config[row.protocol_config_id].append(
                row.credential_id
            )
        protocols_by_site = self._group_protocols(
            rows.protocol_configs,
            models_by_protocol_config,
            sync_targets_by_protocol_config,
            credential_ids_by_protocol_config,
        )

        return [
            SiteConfig(
                id=row.id,
                name=row.name,
                enabled=bool(row.enabled),
                tags=json.loads(row.tags_json),
                base_urls=base_urls_by_site.get(row.id, []),
                credentials=credentials_by_site.get(row.id, []),
                protocols=protocols_by_site.get(row.id, []),
            )
            for row in rows.sites
        ]

    async def _load_sites_by_ids(self, site_ids: list[str]) -> list[SiteConfig]:
        if not site_ids:
            return []
        async with self._session_factory() as session:
            sites = await self._load_sites(session, site_ids=site_ids)
        order = {site_id: index for index, site_id in enumerate(site_ids)}
        return sorted(sites, key=lambda item: order.get(item.id, len(order)))

    async def _site_name_keys(self, session: AsyncSession) -> set[str]:
        rows = (await session.execute(select(SiteEntity.name))).scalars().all()
        return {row.strip().lower() for row in rows if row.strip()}
