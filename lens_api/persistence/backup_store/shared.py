from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ...core.model_prices import normalize_model_key
from ...core.protocol_reachability import can_reach_protocol
from ...core.runtime_channel_ids import (
    compose_runtime_channel_id as _runtime_channel_id,
    extract_protocol_config_id as _extract_protocol_config_id,
    resolve_group_item_runtime_channel_id as _resolve_group_item_channel_id,
    runtime_channel_protocol as _parse_runtime_channel_protocol,
)
from ...core.time_zone import normalize_time_zone, resolve_time_zone
from ...models import (
    ConfigBackupDump,
    ConfigBackupGatewayApiKey,
    ConfigBackupImportedStatsDaily,
    ConfigBackupImportedStatsTotal,
    ConfigBackupOverviewModelDailyStat,
    ConfigBackupRequestLog,
    ConfigBackupRequestLogDailyStat,
    ConfigBackupCronjob,
    ConfigBackupStatsSnapshot,
    ConfigImportResult,
    ModelGroup,
    ModelPriceItem,
    ProtocolKind,
    RequestLogLifecycleStatus,
    SettingItem,
    SiteConfig,
    normalize_upstream_headers_config_json,
)
from ..domain_store import (
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_CORS_ALLOW_ORIGINS,
    SETTING_HEALTH_MIN_SAMPLES,
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_MODEL_LIST_COMPAT_MODE_ENABLED,
    SETTING_PROXY_URL,
    SETTING_RELAY_LOG_KEEP_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_SITE_LOGO_URL,
    SETTING_SITE_NAME,
    SETTING_TIME_ZONE,
    SETTING_MODEL_PRICE_LAST_SYNC_AT,
    SETTING_UPSTREAM_HEADERS_CONFIG,
)
from ..entities import (
    GatewayApiKeyEntity,
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelPriceEntity,
    OverviewModelDailyStatsEntity,
    RequestLogDailyStatsEntity,
    RequestLogEntity,
    CronjobEntity,
    SettingEntity,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)
from ..cronjob_store import (
    encode_weekdays,
    next_cronjob_run_at,
    normalize_cronjob_schedule,
)

BACKUP_DUMP_VERSION = 2
SETTING_STATS_LAST_PERSIST_AT = "stats_last_persist_at"


EXPORTABLE_SETTING_KEYS = (
    SETTING_PROXY_URL,
    SETTING_CORS_ALLOW_ORIGINS,
    SETTING_RELAY_LOG_KEEP_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_HEALTH_MIN_SAMPLES,
    SETTING_MODEL_LIST_COMPAT_MODE_ENABLED,
    SETTING_UPSTREAM_HEADERS_CONFIG,
    SETTING_SITE_NAME,
    SETTING_SITE_LOGO_URL,
    SETTING_TIME_ZONE,
)
