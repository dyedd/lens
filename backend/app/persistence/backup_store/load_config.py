from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backups import ConfigBackupCronjob, ConfigBackupGatewayApiKey
from app.persistence.entities import (
    CronjobEntity,
    GatewayApiKeyEntity,
)

from .value_parsing import (
    format_optional_datetime,
    load_allowed_models,
    load_weekdays,
)


async def _load_gateway_api_keys(
    self, session: AsyncSession
) -> list[ConfigBackupGatewayApiKey]:
    rows = (
        (
            await session.execute(
                select(GatewayApiKeyEntity).order_by(
                    GatewayApiKeyEntity.created_at.asc(),
                    GatewayApiKeyEntity.id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        ConfigBackupGatewayApiKey(
            id=row.id,
            remark=row.remark,
            api_key=row.api_key,
            enabled=bool(row.enabled),
            allowed_models=load_allowed_models(row.allowed_models_json),
            max_cost_usd=max(row.max_cost_usd, 0.0),
            spent_cost_usd=max(row.spent_cost_usd, 0.0),
            expires_at=format_optional_datetime(row.expires_at),
            created_at=format_optional_datetime(row.created_at),
            updated_at=format_optional_datetime(row.updated_at),
        )
        for row in rows
    ]


async def _load_cronjobs(self, session: AsyncSession) -> list[ConfigBackupCronjob]:
    rows = (
        (await session.execute(select(CronjobEntity).order_by(CronjobEntity.id.asc())))
        .scalars()
        .all()
    )
    return [
        ConfigBackupCronjob(
            id=row.id,
            enabled=bool(row.enabled),
            schedule_type=row.schedule_type,
            interval_hours=max(row.interval_hours, 1),
            run_at_time=row.run_at_time,
            weekdays=load_weekdays(row.weekdays_json),
        )
        for row in rows
    ]
