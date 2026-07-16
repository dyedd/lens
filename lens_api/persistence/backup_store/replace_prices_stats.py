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
    json,
    next_cronjob_run_at,
    normalize_cronjob_schedule,
    normalize_model_key,
    resolve_time_zone,
)
from .value_parsing import parse_backup_datetime, parse_optional_datetime


async def _replace_model_prices(
    self, session: AsyncSession, model_prices: list[ModelPriceItem]
) -> None:
    await session.execute(delete(ModelPriceEntity))
    await session.execute(
        delete(SettingEntity).where(
            SettingEntity.key == SETTING_MODEL_PRICE_LAST_SYNC_AT
        )
    )
    model_keys: set[str] = set()
    for item in model_prices:
        model_key = normalize_model_key(item.model_key)
        if not model_key:
            continue
        if model_key in model_keys:
            raise ValueError(f"Duplicate model price key in backup: {model_key}")
        model_keys.add(model_key)
        session.add(
            ModelPriceEntity(
                model_key=model_key,
                display_name=item.display_name or model_key,
                input_price_per_million=item.input_price_per_million,
                output_price_per_million=item.output_price_per_million,
                cache_read_price_per_million=item.cache_read_price_per_million,
                cache_write_price_per_million=item.cache_write_price_per_million,
            )
        )


async def _replace_stats(
    self, session: AsyncSession, stats: ConfigBackupStatsSnapshot
) -> None:
    await session.execute(delete(ImportedStatsDailyEntity))
    await session.execute(delete(ImportedStatsTotalEntity))
    await session.execute(delete(RequestLogDailyStatsEntity))
    await session.execute(delete(OverviewModelDailyStatsEntity))
    if stats.imported_total is not None:
        session.add(
            ImportedStatsTotalEntity(
                id=1,
                input_token=stats.imported_total.input_token,
                output_token=stats.imported_total.output_token,
                input_cost=stats.imported_total.input_cost,
                output_cost=stats.imported_total.output_cost,
                wait_time=stats.imported_total.wait_time,
                request_success=stats.imported_total.request_success,
                request_failed=stats.imported_total.request_failed,
            )
        )

    imported_daily_dates: set[str] = set()
    for item in stats.imported_daily:
        if item.date in imported_daily_dates:
            raise ValueError(f"Duplicate imported stats date in backup: {item.date}")
        imported_daily_dates.add(item.date)
        session.add(
            ImportedStatsDailyEntity(
                date=item.date,
                input_token=item.input_token,
                output_token=item.output_token,
                input_cost=item.input_cost,
                output_cost=item.output_cost,
                wait_time=item.wait_time,
                request_success=item.request_success,
                request_failed=item.request_failed,
            )
        )

    request_daily_dates: set[str] = set()
    for item in stats.request_daily:
        if item.date in request_daily_dates:
            raise ValueError(f"Duplicate request stats date in backup: {item.date}")
        request_daily_dates.add(item.date)
        session.add(
            RequestLogDailyStatsEntity(
                date=item.date,
                request_count=item.request_count,
                successful_requests=item.successful_requests,
                failed_requests=item.failed_requests,
                wait_time_ms=item.wait_time_ms,
                input_tokens=item.input_tokens,
                cache_read_input_tokens=item.cache_read_input_tokens,
                cache_write_input_tokens=item.cache_write_input_tokens,
                output_tokens=item.output_tokens,
                total_tokens=item.total_tokens,
                input_cost_usd=item.input_cost_usd,
                output_cost_usd=item.output_cost_usd,
                total_cost_usd=item.total_cost_usd,
            )
        )

    model_daily_keys: set[tuple[str, str]] = set()
    for item in stats.model_daily:
        key = (item.date, item.model)
        if key in model_daily_keys:
            raise ValueError(
                f"Duplicate model stats row in backup: {item.date} {item.model}"
            )
        model_daily_keys.add(key)
        session.add(
            OverviewModelDailyStatsEntity(
                date=item.date,
                model=item.model,
                requests=item.requests,
                total_tokens=item.total_tokens,
                total_cost_usd=item.total_cost_usd,
            )
        )
