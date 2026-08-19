from __future__ import annotations

from .shared import (
    ProtocolKind,
    SiteBaseUrl,
    SiteBaseUrlEntity,
    SiteCredential,
    SiteCredentialEntity,
    SiteCredentialRateEntity,
    SiteDiscoveredModelEntity,
    SiteModel,
    SiteProtocolConfig,
    SiteProtocolConfigEntity,
    SiteProtocolConfigSyncTargetEntity,
    SiteSyncTarget,
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
                    protocols=_parse_supported_protocols_json(row.protocols_json),
                    enabled=bool(row.enabled),
                    headers=json.loads(row.headers_json),
                    proxy_mode=row.proxy_mode,
                    channel_proxy=row.channel_proxy,
                    param_override=row.param_override,
                    base_url_id=row.base_url_id,
                    credential_ids=credential_ids_by_protocol_config.get(row.id, []),
                    sync_targets=sync_targets_by_protocol_config.get(row.id, []),
                    models=models_by_protocol_config.get(row.id, []),
                )
            )
        return result
