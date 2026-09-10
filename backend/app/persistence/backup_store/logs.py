from __future__ import annotations

import json
from datetime import UTC

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backups import ConfigBackupRequestLog
from app.models.protocols import RequestLogLifecycleStatus
from app.persistence.entities import RequestLogEntity

from .serialize import (
    parse_attempts,
    parse_backup_datetime,
)


async def load_request_logs(
    self, session: AsyncSession
) -> list[ConfigBackupRequestLog]:
    rows = (
        (
            await session.execute(
                select(RequestLogEntity).order_by(
                    RequestLogEntity.created_at.asc(),
                    RequestLogEntity.id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    logs: list[ConfigBackupRequestLog] = []
    for row in rows:
        attempts = parse_attempts(row.attempts_json)
        logs.append(
            ConfigBackupRequestLog(
                protocol=row.protocol,
                user_agent=row.user_agent,
                requested_group_name=row.requested_group_name,
                resolved_group_name=row.resolved_group_name,
                upstream_model_name=row.upstream_model_name,
                channel_id=row.channel_id,
                channel_name=row.channel_name,
                gateway_key_id=row.gateway_key_id,
                status_code=row.status_code,
                success=bool(row.success),
                lifecycle_status=(
                    row.lifecycle_status
                    if row.lifecycle_status
                    in RequestLogLifecycleStatus._value2member_map_
                    else (
                        RequestLogLifecycleStatus.SUCCEEDED.value
                        if row.success
                        else RequestLogLifecycleStatus.FAILED.value
                    )
                ),
                is_stream=bool(row.is_stream),
                first_token_latency_ms=row.first_token_latency_ms,
                latency_ms=row.latency_ms,
                input_tokens=row.input_tokens,
                cache_read_input_tokens=row.cache_read_input_tokens,
                cache_write_input_tokens=row.cache_write_input_tokens,
                output_tokens=row.output_tokens,
                total_tokens=row.total_tokens,
                input_cost_usd=row.input_cost_usd,
                output_cost_usd=row.output_cost_usd,
                total_cost_usd=row.total_cost_usd,
                rate_multiplier=row.rate_multiplier,
                billing_mode=row.billing_mode,
                billing_units=row.billing_units,
                error_message=row.error_message,
                created_at=row.created_at.replace(tzinfo=UTC).isoformat(),
                stats_archived=bool(row.stats_archived),
                request_content=row.request_content,
                response_content=row.response_content,
                attempts=attempts,
            )
        )
    return logs


async def replace_request_logs(
    self, session: AsyncSession, request_logs: list[ConfigBackupRequestLog]
) -> None:
    await session.execute(delete(RequestLogEntity))

    for item in request_logs:
        session.add(
            RequestLogEntity(
                protocol=item.protocol.value,
                user_agent=item.user_agent.strip()[:300],
                requested_group_name=item.requested_group_name,
                resolved_group_name=item.resolved_group_name,
                upstream_model_name=item.upstream_model_name,
                channel_id=item.channel_id,
                channel_name=item.channel_name,
                gateway_key_id=item.gateway_key_id,
                status_code=item.status_code,
                success=1 if item.success else 0,
                lifecycle_status=(
                    item.lifecycle_status or RequestLogLifecycleStatus.FAILED
                ).value,
                is_stream=1 if item.is_stream else 0,
                first_token_latency_ms=max(item.first_token_latency_ms, 0),
                latency_ms=max(item.latency_ms, 0),
                input_tokens=max(item.input_tokens, 0),
                cache_read_input_tokens=max(item.cache_read_input_tokens, 0),
                cache_write_input_tokens=max(item.cache_write_input_tokens, 0),
                output_tokens=max(item.output_tokens, 0),
                total_tokens=max(item.total_tokens, 0),
                input_cost_usd=max(item.input_cost_usd, 0.0),
                output_cost_usd=max(item.output_cost_usd, 0.0),
                total_cost_usd=max(item.total_cost_usd, 0.0),
                rate_multiplier=(
                    max(float(item.rate_multiplier), 0.0)
                    if item.rate_multiplier is not None
                    else None
                ),
                billing_mode=item.billing_mode,
                billing_units=max(item.billing_units, 0),
                request_content=item.request_content,
                response_content=item.response_content,
                attempts_json=json.dumps(
                    [attempt.model_dump(mode="json") for attempt in item.attempts],
                    ensure_ascii=True,
                ),
                error_message=item.error_message,
                stats_archived=1 if item.stats_archived else 0,
                created_at=parse_backup_datetime(item.created_at),
            )
        )
