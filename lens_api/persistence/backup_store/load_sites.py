from __future__ import annotations

from .shared import (
    AsyncSession,
    ConfigBackupCronjob,
    ConfigBackupGatewayApiKey,
    ConfigBackupImportedStatsDaily,
    ConfigBackupImportedStatsTotal,
    ConfigBackupOverviewModelDailyStat,
    ConfigBackupRequestLog,
    ConfigBackupRequestLogDailyStat,
    ConfigBackupStatsSnapshot,
    CronjobEntity,
    GatewayApiKeyEntity,
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    ModelGroup,
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelPriceEntity,
    ModelPriceItem,
    OverviewModelDailyStatsEntity,
    ProtocolKind,
    RequestLogDailyStatsEntity,
    RequestLogEntity,
    RequestLogLifecycleStatus,
    SiteConfig,
    SiteCredentialEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    UTC,
    _extract_protocol_config_id,
    json,
    normalize_model_key,
    select,
)
from .value_parsing import (
    format_optional_datetime,
    load_allowed_models,
    load_weekdays,
    parse_attempts,
)
from ..site_loader import fetch_site_rows


async def _load_sites(self, session: AsyncSession) -> list[SiteConfig]:
    rows = await fetch_site_rows(session)
    if not rows.sites:
        return []

    valid_protocol_values = {protocol_kind.value for protocol_kind in ProtocolKind}
    base_urls_by_site: dict[str, list[dict[str, object]]] = {}
    for row in rows.base_urls:
        base_urls_by_site.setdefault(row.site_id, []).append(
            {
                "id": row.id,
                "url": row.url,
                "name": row.name,
                "enabled": bool(row.enabled),
                "sort_order": row.sort_order,
                "supported_protocols": [
                    p
                    for p in json.loads(row.supported_protocols_json or "[]")
                    if p in valid_protocol_values
                ],
            }
        )

    credentials_by_site: dict[str, list[dict[str, object]]] = {}
    credentials_by_id: dict[str, dict[str, object]] = {}
    for row in rows.credentials:
        item = {
            "id": row.id,
            "name": row.name,
            "api_key": row.api_key,
            "enabled": bool(row.enabled),
            "sort_order": row.sort_order,
        }
        credentials_by_site.setdefault(row.site_id, []).append(item)
        credentials_by_id[row.id] = item

    models_by_protocol_config: dict[str, list[dict[str, object]]] = {}
    for row in rows.discovered_models:
        credential_name = str(
            credentials_by_id.get(row.credential_id, {}).get("name", "")
        )
        models_by_protocol_config.setdefault(row.protocol_config_id, []).append(
            {
                "id": row.id,
                "credential_id": row.credential_id,
                "credential_name": credential_name,
                "model_name": row.model_name,
                "enabled": bool(row.enabled),
                "sort_order": row.sort_order,
                "protocol": (
                    row.protocol if row.protocol in valid_protocol_values else None
                ),
            }
        )

    protocol_configs_by_site: dict[str, list[dict[str, object]]] = {}
    for row in rows.protocol_configs:
        raw_headers = json.loads(row.headers_json)
        if not isinstance(raw_headers, dict):
            raise ValueError(f"Invalid headers JSON for protocol config {row.id}")
        headers = {str(key): str(value) for key, value in raw_headers.items()}

        protocol_configs_by_site.setdefault(row.site_id, []).append(
            {
                "id": row.id,
                "name": row.name,
                "protocols": [
                    p
                    for p in json.loads(row.protocols_json or "[]")
                    if p in valid_protocol_values
                ],
                "enabled": bool(row.enabled),
                "headers": headers,
                "proxy_mode": row.proxy_mode,
                "channel_proxy": row.channel_proxy,
                "param_override": row.param_override,
                "match_regex": row.match_regex,
                "base_url_id": row.base_url_id,
                "credential_id": row.credential_id,
                "auto_sync_enabled": bool(row.auto_sync_enabled),
                "models": models_by_protocol_config.get(row.id, []),
            }
        )

    return [
        SiteConfig.model_validate(
            {
                "id": row.id,
                "name": row.name,
                "base_urls": base_urls_by_site.get(row.id, []),
                "credentials": credentials_by_site.get(row.id, []),
                "protocols": protocol_configs_by_site.get(row.id, []),
            }
        )
        for row in rows.sites
    ]
