from __future__ import annotations

from ...core.runtime_channel_ids import compose_runtime_channel_id
from .shared import (
    AsyncSession,
    ChannelConfig,
    ChannelDiscoveredModel,
    ChannelKeyItem,
    ChannelStatus,
    ProtocolKind,
    SiteBaseUrl,
    SiteBaseUrlEntity,
    SiteBaseUrlInput,
    SiteConfig,
    SiteCredential,
    SiteCredentialEntity,
    SiteCredentialInput,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteModel,
    SiteProtocolConfig,
    SiteProtocolConfigEntity,
    _parse_protocols_json,
    defaultdict,
    json,
    select,
    uuid,
)


class ChannelNormalizationMixin:
    def _flatten_site(self, site: SiteConfig) -> list[ChannelConfig]:
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
                        name=site.name,
                        protocol=protocol,
                        base_url=bound_base_url.url,
                        api_key=active_key.key,
                        status=(
                            ChannelStatus.ENABLED
                            if protocol_config.enabled
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
                        channel_proxy=protocol_config.channel_proxy,
                        param_override=protocol_config.param_override,
                        match_regex=protocol_config.match_regex,
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
        credential_ids = list(
            dict.fromkeys(
                [protocol_config.credential_id]
                + [item.credential_id for item in protocol_config.models]
            )
        )
        return [
            ChannelKeyItem(
                id=credential.id,
                key=credential.api_key,
                remark=credential.name,
                enabled=credential.enabled,
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

    def _normalize_credentials(
        self, items: list[SiteCredentialInput]
    ) -> list[SiteCredential]:
        normalized: list[SiteCredential] = []
        seen_names: set[str] = set()
        for index, item in enumerate(items):
            name = item.name.strip()
            if not name:
                raise ValueError("Credential name is required")
            name_key = name.lower()
            if name_key in seen_names:
                raise ValueError(f"Duplicate credential name: {name}")
            seen_names.add(name_key)
            normalized.append(
                SiteCredential(
                    id=item.id or str(uuid.uuid4()),
                    name=name,
                    api_key=item.api_key,
                    enabled=item.enabled,
                    sort_order=index,
                )
            )
        if not normalized:
            raise ValueError("At least one credential is required")
        return normalized

    def _normalize_base_urls(self, items: list[SiteBaseUrlInput]) -> list[SiteBaseUrl]:
        normalized: list[SiteBaseUrl] = []
        for index, item in enumerate(items):
            url_str = str(item.url).strip()
            if not url_str:
                raise ValueError("Base URL is required")
            normalized.append(
                SiteBaseUrl(
                    id=item.id or str(uuid.uuid4()),
                    url=item.url,
                    name=item.name.strip(),
                    enabled=item.enabled,
                    sort_order=index,
                    supported_protocols=list(dict.fromkeys(item.supported_protocols)),
                )
            )
        return normalized

    async def _ensure_site_name_unique(
        self, session: AsyncSession, name: str, exclude_site_id: str | None = None
    ) -> None:
        normalized_name = name.strip()
        result = await session.execute(
            select(SiteEntity).where(SiteEntity.name == normalized_name).limit(1)
        )
        row = result.scalar_one_or_none()
        if row is not None and row.id != exclude_site_id:
            raise ValueError(f"Site already exists: {normalized_name}")

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
                    supported_protocols=_parse_protocols_json(
                        row.supported_protocols_json
                    ),
                )
            )
        return result

    def _group_credentials(
        self, rows: list[SiteCredentialEntity]
    ) -> tuple[dict[str, list[SiteCredential]], dict[str, SiteCredential]]:
        by_site: dict[str, list[SiteCredential]] = defaultdict(list)
        by_id: dict[str, SiteCredential] = {}
        for row in rows:
            item = SiteCredential(
                id=row.id,
                name=row.name,
                api_key=row.api_key,
                enabled=bool(row.enabled),
                sort_order=row.sort_order,
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
        valid_protocol_values = {pk.value for pk in ProtocolKind}
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
                )
            )
        return result

    def _group_protocols(
        self,
        rows: list[SiteProtocolConfigEntity],
        models_by_protocol_config: dict[str, list[SiteModel]],
    ) -> dict[str, list[SiteProtocolConfig]]:
        result: dict[str, list[SiteProtocolConfig]] = defaultdict(list)
        for row in rows:
            result[row.site_id].append(
                SiteProtocolConfig(
                    id=row.id,
                    name=row.name,
                    protocols=_parse_protocols_json(row.protocols_json),
                    enabled=bool(row.enabled),
                    headers=json.loads(row.headers_json),
                    channel_proxy=row.channel_proxy,
                    param_override=row.param_override,
                    match_regex=row.match_regex,
                    base_url_id=row.base_url_id,
                    credential_id=row.credential_id,
                    models=models_by_protocol_config.get(row.id, []),
                )
            )
        return result
