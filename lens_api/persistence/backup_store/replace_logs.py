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


async def _replace_request_logs(
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
