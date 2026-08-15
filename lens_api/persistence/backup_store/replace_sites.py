from __future__ import annotations

import uuid

from .shared import (
    AsyncSession,
    ConfigBackupCronjob,
    ConfigBackupGatewayApiKey,
    ConfigBackupRequestLog,
    ConfigBackupStatsSnapshot,
    CronjobEntity,
    EXPORTABLE_SETTING_KEYS,
    GatewayApiKeyEntity,
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    ModelGroup,
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelPriceEntity,
    ModelPriceItem,
    ModelSource,
    OverviewModelDailyStatsEntity,
    ProtocolKind,
    RequestLogDailyStatsEntity,
    RequestLogEntity,
    RequestLogLifecycleStatus,
    SETTING_MODEL_PRICE_LAST_SYNC_AT,
    SETTING_TIME_ZONE,
    SettingEntity,
    SettingItem,
    SiteBaseUrlEntity,
    SiteConfig,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    SiteProtocolConfigCredentialEntity,
    SiteProtocolConfigSyncTargetEntity,
    UTC,
    _extract_protocol_config_id,
    _parse_runtime_channel_protocol,
    _resolve_group_item_channel_id,
    _runtime_channel_id,
    can_reach_protocol,
    datetime,
    delete,
    encode_weekdays,
    json,
    next_cronjob_run_at,
    normalize_cronjob_schedule,
    normalize_model_key,
    resolve_time_zone,
)
from .value_parsing import parse_backup_datetime, parse_optional_datetime


async def _replace_sites(
    self, session: AsyncSession, sites: list[SiteConfig]
) -> tuple[set[str], dict[str, list[ProtocolKind]], set[tuple[str, str, str]]]:
    await session.execute(delete(SiteDiscoveredModelEntity))
    await session.execute(delete(SiteProtocolConfigCredentialEntity))
    await session.execute(delete(SiteProtocolConfigEntity))
    await session.execute(delete(SiteCredentialEntity))
    await session.execute(delete(SiteBaseUrlEntity))
    await session.execute(delete(SiteEntity))

    site_ids: set[str] = set()
    site_names: set[str] = set()
    protocol_config_ids: set[str] = set()
    protocols_by_config_id: dict[str, list[ProtocolKind]] = {}
    credential_ids: set[str] = set()
    model_keys: set[tuple[str, str, str]] = set()
    base_url_ids: set[str] = set()
    model_ids: set[str] = set()

    for site in sites:
        if site.id in site_ids:
            raise ValueError(f"Duplicate site id in backup: {site.id}")
        if site.name in site_names:
            raise ValueError(f"Duplicate site name in backup: {site.name}")
        site_ids.add(site.id)
        site_names.add(site.name)

        session.add(
            SiteEntity(
                id=site.id,
                name=site.name,
                enabled=int(site.enabled),
                tags_json=json.dumps(site.tags, ensure_ascii=True),
            )
        )
        site_base_url_ids: set[str] = set()
        site_credential_ids: set[str] = set()

        for base_url in site.base_urls:
            if base_url.id in base_url_ids:
                raise ValueError(f"Duplicate base url id in backup: {base_url.id}")
            base_url_ids.add(base_url.id)
            site_base_url_ids.add(base_url.id)
            session.add(
                SiteBaseUrlEntity(
                    id=base_url.id,
                    site_id=site.id,
                    url=str(base_url.url),
                    name=base_url.name,
                    enabled=1 if base_url.enabled else 0,
                    sort_order=base_url.sort_order,
                    supported_protocols_json=json.dumps(
                        [p.value for p in (base_url.supported_protocols or [])],
                        ensure_ascii=True,
                    ),
                )
            )

        for credential in site.credentials:
            if credential.id in credential_ids:
                raise ValueError(f"Duplicate credential id in backup: {credential.id}")
            credential_ids.add(credential.id)
            site_credential_ids.add(credential.id)
            session.add(
                SiteCredentialEntity(
                    id=credential.id,
                    site_id=site.id,
                    name=credential.name,
                    api_key=credential.api_key,
                    enabled=1 if credential.enabled else 0,
                    sort_order=credential.sort_order,
                )
            )

        for protocol_config in site.protocols:
            if protocol_config.id in protocol_config_ids:
                raise ValueError(
                    "Duplicate protocol config id in backup: " f"{protocol_config.id}"
                )
            protocol_config_ids.add(protocol_config.id)
            if protocol_config.base_url_id not in site_base_url_ids:
                raise ValueError(
                    "Protocol config base URL not found in backup site "
                    f"{site.name}: {protocol_config.base_url_id}"
                )
            missing_credential_ids = (
                set(protocol_config.credential_ids) - site_credential_ids
            )
            if missing_credential_ids:
                raise ValueError(
                    "Protocol config credentials not found in backup site "
                    f"{site.name}: {', '.join(sorted(missing_credential_ids))}"
                )
            protocol_kinds = list(protocol_config.protocols)
            if not protocol_kinds:
                raise ValueError(
                    "Protocol config protocols not found in backup site "
                    f"{site.name}: {protocol_config.id}"
                )
            session.add(
                SiteProtocolConfigEntity(
                    id=protocol_config.id,
                    site_id=site.id,
                    name=protocol_config.name,
                    protocols_json=json.dumps(
                        [p.value for p in protocol_kinds],
                        ensure_ascii=True,
                    ),
                    enabled=1 if protocol_config.enabled else 0,
                    headers_json=json.dumps(protocol_config.headers, ensure_ascii=True),
                    proxy_mode=protocol_config.proxy_mode.value,
                    channel_proxy=protocol_config.channel_proxy,
                    param_override=protocol_config.param_override,
                    base_url_id=protocol_config.base_url_id,
                )
            )
            for sort_order, credential_id in enumerate(protocol_config.credential_ids):
                session.add(
                    SiteProtocolConfigCredentialEntity(
                        id=str(uuid.uuid4()),
                        protocol_config_id=protocol_config.id,
                        credential_id=credential_id,
                        sort_order=sort_order,
                    )
                )

            protocols_by_config_id[protocol_config.id] = protocol_kinds

            target_keys: set[tuple[str, str, ProtocolKind]] = set()
            for target in protocol_config.sync_targets:
                target_key = (
                    target.credential_id,
                    target.model_name,
                    target.protocol,
                )
                if (
                    target.credential_id not in site_credential_ids
                    or target.protocol not in protocol_kinds
                    or not target.model_name
                    or target_key in target_keys
                ):
                    raise ValueError(
                        "Invalid sync target in backup protocol config "
                        f"{protocol_config.id}: {target.model_name}"
                    )
                target_keys.add(target_key)
                session.add(
                    SiteProtocolConfigSyncTargetEntity(
                        id=str(uuid.uuid4()),
                        protocol_config_id=protocol_config.id,
                        credential_id=target.credential_id,
                        protocol=target.protocol.value,
                        model_name=target.model_name,
                    )
                )

            for model in protocol_config.models:
                if model.id in model_ids:
                    raise ValueError(
                        f"Duplicate discovered model id in backup: {model.id}"
                    )
                model_ids.add(model.id)
                if (
                    not model.credential_id
                    or model.credential_id not in site_credential_ids
                ):
                    raise ValueError(
                        "Discovered model credential not found in backup site "
                        f"{site.name}: {model.credential_id}"
                    )
                if model.protocol is None:
                    raise ValueError(
                        "Discovered model protocol not found in backup site "
                        f"{site.name}: {model.model_name}"
                    )
                if model.protocol not in protocols_by_config_id[protocol_config.id]:
                    raise ValueError(
                        "Discovered model protocol is not enabled in backup "
                        f"protocol config {protocol_config.id}: "
                        f"{model.protocol.value}"
                    )
                target_key = (
                    model.credential_id,
                    model.model_name,
                    model.protocol,
                )
                if (model.source == ModelSource.SYNCED) != (target_key in target_keys):
                    raise ValueError(
                        "Model source does not match sync targets in backup "
                        f"protocol config {protocol_config.id}: {model.model_name}"
                    )
                model_keys.add(
                    (
                        _runtime_channel_id(protocol_config.id, model.protocol),
                        model.credential_id,
                        model.model_name,
                    )
                )
                session.add(
                    SiteDiscoveredModelEntity(
                        id=model.id,
                        protocol_config_id=protocol_config.id,
                        credential_id=model.credential_id,
                        model_name=model.model_name,
                        enabled=1 if model.enabled else 0,
                        sort_order=model.sort_order,
                        protocol=model.protocol.value,
                        source=model.source.value,
                    )
                )

    return protocol_config_ids, protocols_by_config_id, model_keys
