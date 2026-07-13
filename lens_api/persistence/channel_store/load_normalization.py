from __future__ import annotations

from .shared import (
    ProtocolKind,
    SiteBaseUrl,
    SiteBaseUrlEntity,
    SiteCredential,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteModel,
    SiteProtocolConfig,
    SiteProtocolConfigEntity,
    defaultdict,
    json,
)
from ..shared import _parse_supported_protocols_json


class ChannelLoadNormalizationMixin:
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
                    supported_protocols=_parse_supported_protocols_json(
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
                    protocols=_parse_supported_protocols_json(row.protocols_json),
                    enabled=bool(row.enabled),
                    headers=json.loads(row.headers_json),
                    proxy_mode=row.proxy_mode,
                    channel_proxy=row.channel_proxy,
                    param_override=row.param_override,
                    match_regex=row.match_regex,
                    base_url_id=row.base_url_id,
                    credential_id=row.credential_id,
                    auto_sync_enabled=bool(row.auto_sync_enabled),
                    models=models_by_protocol_config.get(row.id, []),
                )
            )
        return result
