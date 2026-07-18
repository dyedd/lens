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
from ...core.time_zone import resolve_time_zone
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
    ModelGroupItem,
    ModelPriceItem,
    ProtocolKind,
    RequestLogLifecycleStatus,
    SettingItem,
    SiteConfig,
)
from ..editable_settings import (
    EDITABLE_SETTING_KEYS,
    effective_editable_setting_items,
    normalize_editable_setting_items,
)
from ..shared import SETTING_MODEL_PRICE_LAST_SYNC_AT, SETTING_TIME_ZONE
from ..entities import (
    GatewayApiKeyEntity,
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelPriceEntity,
    RequestLogEntity,
    CronjobEntity,
    SettingEntity,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)
from ..stats_entities import (
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    OverviewModelDailyStatsEntity,
    RequestLogDailyStatsEntity,
)
from ..cronjob_store import (
    encode_weekdays,
    next_cronjob_run_at,
    normalize_cronjob_schedule,
)

BACKUP_DUMP_VERSION = 2
EXPORTABLE_SETTING_KEYS = EDITABLE_SETTING_KEYS
