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


async def _load_request_logs(
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
                error_message=row.error_message,
                created_at=row.created_at.replace(tzinfo=UTC).isoformat(),
                stats_archived=bool(row.stats_archived),
                request_content=row.request_content,
                response_content=row.response_content,
                attempts=attempts,
            )
        )
    return logs
