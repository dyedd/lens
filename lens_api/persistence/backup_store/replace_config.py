from __future__ import annotations

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
    UTC,
    _extract_protocol_config_id,
    _parse_runtime_channel_protocol,
    _resolve_group_item_channel_id,
    _runtime_channel_id,
    can_reach_protocol,
    datetime,
    delete,
    encode_weekdays,
    effective_editable_setting_items,
    json,
    next_cronjob_run_at,
    normalize_cronjob_schedule,
    normalize_model_key,
    normalize_editable_setting_items,
    resolve_time_zone,
)
from .value_parsing import parse_backup_datetime, parse_optional_datetime


async def _replace_settings(
    self, session: AsyncSession, settings: list[SettingItem]
) -> int:
    await session.execute(
        delete(SettingEntity).where(SettingEntity.key.in_(EXPORTABLE_SETTING_KEYS))
    )
    setting_keys: set[str] = set()
    imported_settings: list[SettingItem] = []
    for item in settings:
        if item.key not in EXPORTABLE_SETTING_KEYS:
            continue
        if item.key in setting_keys:
            raise ValueError(f"Duplicate setting key in backup: {item.key}")
        setting_keys.add(item.key)
        imported_settings.append(item)
    normalized_items = normalize_editable_setting_items(imported_settings)
    effective_items = effective_editable_setting_items(normalized_items)
    for item in effective_items:
        session.add(SettingEntity(key=item.key, value=item.value))
    return len(effective_items)


async def _replace_cronjobs(
    self, session: AsyncSession, cronjobs: list[ConfigBackupCronjob]
) -> None:
    task_ids: set[str] = set()
    now = datetime.now(UTC).replace(tzinfo=None)
    time_zone_setting = await session.get(SettingEntity, SETTING_TIME_ZONE)
    time_zone = resolve_time_zone(
        time_zone_setting.value if time_zone_setting is not None else None
    )
    for item in cronjobs:
        task_id = item.id.strip()
        if not task_id:
            continue
        if task_id in task_ids:
            raise ValueError(f"Duplicate cron job id in backup: {task_id}")
        task_ids.add(task_id)
        schedule = normalize_cronjob_schedule(
            schedule_type=item.schedule_type.value,
            interval_hours=item.interval_hours,
            run_at_time=item.run_at_time,
            weekdays=item.weekdays,
        )
        next_run_at = (
            next_cronjob_run_at(schedule, now=now, time_zone=time_zone)
            if item.enabled
            else None
        )

        entity = await session.get(CronjobEntity, task_id)
        if entity is None:
            session.add(
                CronjobEntity(
                    id=task_id,
                    enabled=1 if item.enabled else 0,
                    schedule_type=schedule.schedule_type,
                    interval_hours=schedule.interval_hours,
                    run_at_time=schedule.run_at_time,
                    weekdays_json=encode_weekdays(schedule.weekdays),
                    status="idle" if item.enabled else "disabled",
                    last_error="",
                    next_run_at=next_run_at,
                    lease_owner="",
                    created_at=now,
                    updated_at=now,
                )
            )
            continue

        entity.enabled = 1 if item.enabled else 0
        entity.schedule_type = schedule.schedule_type
        entity.interval_hours = schedule.interval_hours
        entity.run_at_time = schedule.run_at_time
        entity.weekdays_json = encode_weekdays(schedule.weekdays)
        entity.next_run_at = next_run_at
        if not entity.lease_owner:
            entity.status = "idle" if item.enabled else "disabled"
        entity.updated_at = now


async def _replace_gateway_api_keys(
    self, session: AsyncSession, gateway_api_keys: list[ConfigBackupGatewayApiKey]
) -> None:
    await session.execute(delete(GatewayApiKeyEntity))
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    now = datetime.now(UTC).replace(tzinfo=None)

    for item in gateway_api_keys:
        key_id = item.id.strip()
        api_key = item.api_key.strip()
        if not key_id:
            raise ValueError("Gateway API key id is required")
        if not api_key:
            raise ValueError("Gateway API key secret is required")
        if key_id in seen_ids:
            raise ValueError(f"Duplicate gateway API key id in backup: {key_id}")
        if api_key in seen_keys:
            raise ValueError("Duplicate gateway API key secret in backup")
        seen_ids.add(key_id)
        seen_keys.add(api_key)

        session.add(
            GatewayApiKeyEntity(
                id=key_id,
                remark=item.remark.strip(),
                api_key=api_key,
                enabled=1 if item.enabled else 0,
                allowed_models_json=json.dumps(
                    item.allowed_models,
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
                max_cost_usd=max(item.max_cost_usd, 0.0),
                spent_cost_usd=max(item.spent_cost_usd, 0.0),
                expires_at=parse_optional_datetime(item.expires_at),
                created_at=parse_optional_datetime(item.created_at) or now,
                updated_at=parse_optional_datetime(item.updated_at) or now,
            )
        )
