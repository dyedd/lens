from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_prices import canonical_model_price_key
from app.models.backups import (
    ConfigBackupImportedStatsDaily,
    ConfigBackupImportedStatsTotal,
    ConfigBackupOverviewModelDailyStat,
    ConfigBackupRequestLogDailyStat,
    ConfigBackupStatsSnapshot,
)
from app.models.model_prices import ModelPriceItem
from app.persistence.entities import (
    ModelPriceEntity,
    SettingEntity,
)
from app.persistence.settings_keys import SETTING_MODEL_PRICE_LAST_SYNC_AT
from app.persistence.stats_entities import (
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    OverviewModelDailyStatsEntity,
    RequestLogDailyStatsEntity,
)


async def load_model_prices(self, session: AsyncSession) -> list[ModelPriceItem]:
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
            image_price_per_image=row.image_price_per_image,
            pricing_mode=row.pricing_mode,
        )
        for row in rows
    ]


async def load_stats(self, session: AsyncSession) -> ConfigBackupStatsSnapshot:
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


async def replace_model_prices(
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
        model_key = canonical_model_price_key(item.model_key)
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
                image_price_per_image=item.image_price_per_image,
                pricing_mode=item.pricing_mode,
            )
        )


async def replace_stats(
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
