from __future__ import annotations

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
)
from app.persistence.entities import (
    SiteCredentialEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)

from ...core.runtime_channel_ids import compose_runtime_channel_id
from ..site_loader import (
    build_site_configs,
    fetch_site_rows,
)


class SiteChannelProjectionMixin:
    def flatten_site(self, site: SiteConfig) -> list[ChannelConfig]:
        credentials_by_id = {item.id: item for item in site.credentials}
        base_urls_by_id = {item.id: item for item in site.base_urls}
        model_list_url = next(
            (item.url for item in site.base_urls if item.kind == "models"), None
        )
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
            active_key = keys[0]
            models_by_protocol = self._models_by_protocol(protocol_config.models)
            for protocol in protocols:
                protocol_models = models_by_protocol.get(protocol, [])
                items.append(
                    ChannelConfig(
                        id=compose_runtime_channel_id(protocol_config.id, protocol),
                        site_id=site.id,
                        site_tags=list(site.tags),
                        name=site.name,
                        protocol=protocol,
                        base_url=bound_base_url.url,
                        endpoint_kind=bound_base_url.kind,
                        model_list_url=model_list_url,
                        api_key=active_key.key,
                        status=(
                            ChannelStatus.ENABLED
                            if site.enabled
                            else ChannelStatus.DISABLED
                        ),
                        headers=site.headers,
                        model_patterns=[
                            m.model_name for m in protocol_models if m.enabled
                        ],
                        keys=keys,
                        models=self._build_channel_models(
                            protocol_models,
                            credentials_by_id,
                        ),
                        proxy_mode=site.proxy_mode,
                        channel_proxy=site.channel_proxy,
                        param_override=site.param_override,
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
                    context_window=model.context_window,
                    upstream_context_window=model.upstream_context_window,
                )
            )
        return items

    def _build_credentials(
        self, items: list[SiteCredentialInput], base_url_ids: set[str]
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
            base_url_id = item.base_url_id.strip()
            if base_url_id and base_url_id not in base_url_ids:
                raise ValueError(f"Credential base URL not found: {base_url_id}")
            built_credentials.append(
                SiteCredential(
                    id=item.id or str(uuid.uuid4()),
                    name=name,
                    api_key=item.api_key,
                    sort_order=index,
                    base_url_id=base_url_id,
                    model_pattern=item.model_pattern,
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
        seen_kinds: set[str] = set()
        for index, item in enumerate(items):
            url_str = str(item.url).strip()
            if not url_str:
                raise ValueError("Base URL is required")
            if item.kind in seen_kinds:
                raise ValueError(f"Duplicate endpoint purpose: {item.kind}")
            seen_kinds.add(item.kind)
            built_base_urls.append(
                SiteBaseUrl(
                    id=item.id or str(uuid.uuid4()),
                    url=item.url,
                    sort_order=index,
                    kind=item.kind,
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
        sites = build_site_configs(rows)
        return sites

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
