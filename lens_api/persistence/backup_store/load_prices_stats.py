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


async def _load_model_prices(self, session: AsyncSession) -> list[ModelPriceItem]:
    rows = (
        (
            await session.execute(
                select(ModelPriceEntity).order_by(
                    ModelPriceEntity.display_name.asc(),
                    ModelPriceEntity.model_key.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        ModelPriceItem(
            model_key=row.model_key,
            display_name=row.display_name,
            protocols=[],
            input_price_per_million=row.input_price_per_million,
            output_price_per_million=row.output_price_per_million,
            cache_read_price_per_million=row.cache_read_price_per_million,
            cache_write_price_per_million=row.cache_write_price_per_million,
        )
        for row in rows
    ]


async def _load_stats(self, session: AsyncSession) -> ConfigBackupStatsSnapshot:
    imported_total_row = await session.get(ImportedStatsTotalEntity, 1)
    imported_daily_rows = (
        (
            await session.execute(
                select(ImportedStatsDailyEntity).order_by(
                    ImportedStatsDailyEntity.date.asc()
                )
            )
        )
        .scalars()
        .all()
    )
    request_daily_rows = (
        (
            await session.execute(
                select(RequestLogDailyStatsEntity).order_by(
                    RequestLogDailyStatsEntity.date.asc()
                )
            )
        )
        .scalars()
        .all()
    )
    model_daily_rows = (
        (
            await session.execute(
                select(OverviewModelDailyStatsEntity).order_by(
                    OverviewModelDailyStatsEntity.date.asc(),
                    OverviewModelDailyStatsEntity.model.asc(),
                )
            )
        )
        .scalars()
        .all()
    )

    imported_total = None
    if imported_total_row is not None:
        imported_total = ConfigBackupImportedStatsTotal(
            input_token=imported_total_row.input_token,
            output_token=imported_total_row.output_token,
            input_cost=imported_total_row.input_cost,
            output_cost=imported_total_row.output_cost,
            wait_time=imported_total_row.wait_time,
            request_success=imported_total_row.request_success,
            request_failed=imported_total_row.request_failed,
        )

    return ConfigBackupStatsSnapshot(
        imported_total=imported_total,
        imported_daily=[
            ConfigBackupImportedStatsDaily(
                date=row.date,
                input_token=row.input_token,
                output_token=row.output_token,
                input_cost=row.input_cost,
                output_cost=row.output_cost,
                wait_time=row.wait_time,
                request_success=row.request_success,
                request_failed=row.request_failed,
            )
            for row in imported_daily_rows
        ],
        request_daily=[
            ConfigBackupRequestLogDailyStat(
                date=row.date,
                request_count=row.request_count,
                successful_requests=row.successful_requests,
                failed_requests=row.failed_requests,
                wait_time_ms=row.wait_time_ms,
                input_tokens=row.input_tokens,
                cache_read_input_tokens=row.cache_read_input_tokens,
                cache_write_input_tokens=row.cache_write_input_tokens,
                output_tokens=row.output_tokens,
                total_tokens=row.total_tokens,
                input_cost_usd=row.input_cost_usd,
                output_cost_usd=row.output_cost_usd,
                total_cost_usd=row.total_cost_usd,
            )
            for row in request_daily_rows
        ],
        model_daily=[
            ConfigBackupOverviewModelDailyStat(
                date=row.date,
                model=row.model,
                requests=row.requests,
                total_tokens=row.total_tokens,
                total_cost_usd=row.total_cost_usd,
            )
            for row in model_daily_rows
        ],
    )
