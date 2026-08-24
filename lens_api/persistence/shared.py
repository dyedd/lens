from __future__ import annotations

import asyncio
import json
import logging
import secrets
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import String, cast, delete, func, literal, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..core.model_prices import normalize_model_key
from ..core.runtime_channel_ids import (
    compose_runtime_channel_id as _runtime_channel_id,
    split_runtime_channel_id as _parse_runtime_channel_id,
)
from ..core.time_zone import normalize_time_zone, resolve_time_zone
from ..models import (
    ChannelConfig,
    ChannelStatus,
    GatewayApiKey,
    GatewayApiKeyCreate,
    GatewayApiKeyUpdate,
    ModelGroup,
    ModelGroupCandidateItem,
    ModelGroupCandidateSubitem,
    ModelGroupCandidatesRequest,
    ModelGroupCandidatesResponse,
    ModelGroupCreate,
    ModelGroupEnsureFromSiteRequest,
    ModelGroupEnsureFromSiteResponse,
    ModelGroupEnsureModelInput,
    ModelGroupEnsureResultItem,
    ModelGroupItem,
    ModelGroupItemInput,
    ModelGroupItemView,
    ModelGroupUpdate,
    ModelGroupView,
    HealthBucket,
    HealthItem,
    HealthSummary,
    ModelPriceItem,
    ModelPriceListResponse,
    ModelPriceUpdate,
    OverviewDailyPoint,
    OverviewModelAnalytics,
    OverviewModelMetricPoint,
    OverviewModelTrendPoint,
    OverviewSummary,
    OverviewSummaryMetric,
    ProtocolKind,
    RequestLogAttempt,
    RequestLogDetail,
    RequestLogFilterOption,
    RequestLogItem,
    RequestLogLifecycleStatus,
    RequestLogPage,
    RequestLogSortMode,
    RequestLogStatusFilter,
    SettingItem,
)
from ..core.protocol_reachability import can_reach_protocol
from .entities import (
    GatewayApiKeyEntity,
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelPriceEntity,
    RequestLogEntity,
    SettingEntity,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    SiteProtocolConfigCredentialEntity,
)
from .stats_entities import (
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    OverviewModelDailyStatsEntity,
    RequestLogDailyStatsEntity,
)

_LOGGER = logging.getLogger(__name__)
_PROTOCOL_KIND_BY_VALUE = {protocol.value: protocol for protocol in ProtocolKind}


def _parse_supported_protocols_json(raw: str | None) -> list[ProtocolKind]:
    try:
        values = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(values, list):
        return []

    protocols: list[ProtocolKind] = []
    for value in values:
        protocol = _PROTOCOL_KIND_BY_VALUE.get(str(value))
        if protocol is None:
            continue
        if protocol not in protocols:
            protocols.append(protocol)
    return protocols


def _channel_ids_by_protocol_config(
    channel_ids: Iterable[str | None],
) -> tuple[dict[str, list[str]], dict[str, ProtocolKind]]:
    channels_by_protocol_config: dict[str, list[str]] = {}
    protocol_by_channel_id: dict[str, ProtocolKind] = {}
    seen_channel_ids: set[str] = set()

    for raw_channel_id in channel_ids:
        channel_id = raw_channel_id.strip() if isinstance(raw_channel_id, str) else ""
        if not channel_id or channel_id in seen_channel_ids:
            continue
        seen_channel_ids.add(channel_id)

        parsed = _parse_runtime_channel_id(channel_id)
        protocol_config_id = parsed[0] if parsed else channel_id
        if parsed is not None:
            protocol_by_channel_id[channel_id] = parsed[1]
        channels_by_protocol_config.setdefault(protocol_config_id, []).append(
            channel_id
        )

    return channels_by_protocol_config, protocol_by_channel_id


SETTING_MODEL_PRICE_LAST_SYNC_AT = "model_price_last_sync_at"
SETTING_AUTH_ACCESS_TOKEN_MINUTES = "auth_access_token_minutes"
SETTING_PROXY_URL = "proxy_url"
SETTING_STATS_TIME_ZONE = "stats_time_zone"
SETTING_TIME_ZONE = "time_zone"
SETTING_CORS_ALLOW_ORIGINS = "cors_allow_origins"
SETTING_RELAY_LOG_BODY_ENABLED = "relay_log_body_enabled"
SETTING_RELAY_LOG_KEEP_ENABLED = "relay_log_keep_enabled"
SETTING_RELAY_LOG_KEEP_PERIOD = "relay_log_keep_period"
SETTING_CIRCUIT_BREAKER_THRESHOLD = "circuit_breaker_threshold"
SETTING_CIRCUIT_BREAKER_FAILURE_WINDOW = "circuit_breaker_failure_window_seconds"
SETTING_CIRCUIT_BREAKER_TIMEOUT_THRESHOLD = "circuit_breaker_timeout_threshold"
SETTING_CIRCUIT_BREAKER_NETWORK_THRESHOLD = "circuit_breaker_network_threshold"
SETTING_CIRCUIT_BREAKER_COOLDOWN = "circuit_breaker_cooldown"
SETTING_CIRCUIT_BREAKER_AUTH_COOLDOWN = "circuit_breaker_auth_cooldown"
SETTING_CIRCUIT_BREAKER_NOT_FOUND_COOLDOWN = "circuit_breaker_not_found_cooldown"
SETTING_CIRCUIT_BREAKER_RATE_LIMIT_COOLDOWN = "circuit_breaker_rate_limit_cooldown"
SETTING_CIRCUIT_BREAKER_TIMEOUT_COOLDOWN = "circuit_breaker_timeout_cooldown"
SETTING_CIRCUIT_BREAKER_NETWORK_COOLDOWN = "circuit_breaker_network_cooldown"
SETTING_CIRCUIT_BREAKER_BACKOFF_MULTIPLIER = "circuit_breaker_backoff_multiplier"
SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN = "circuit_breaker_max_cooldown"
SETTING_HEALTH_SCORING_ENABLED = "health_scoring_enabled"
SETTING_HEALTH_WINDOW_SECONDS = "health_window_seconds"
SETTING_HEALTH_PENALTY_WEIGHT = "health_penalty_weight"
SETTING_HEALTH_MIN_SAMPLES = "health_min_samples"
SETTING_MODEL_LIST_COMPAT_MODE_ENABLED = "model_list_compat_mode_enabled"
SETTING_FIRST_TOKEN_TIMEOUT_SECONDS = "first_token_timeout_seconds"
SETTING_STREAM_IDLE_TIMEOUT_SECONDS = "stream_idle_timeout_seconds"
SETTING_MAX_REQUEST_BODY_BYTES = "max_request_body_bytes"
SETTING_MODEL_TEST_PROMPTS = "model_test_prompts"
SETTING_UPSTREAM_HEADERS_CONFIG = "upstream_headers_config"
SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG = "upstream_param_override_config"
SETTING_SITE_NAME = "site_name"
SETTING_SITE_LOGO_URL = "site_logo_url"
SETTING_LATEST_VERSION = "latest_version"
SETTING_LATEST_VERSION_URL = "latest_version_url"
SETTING_VERSION_CHECK_AT = "version_check_at"
GATEWAY_API_KEY_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
REQUEST_LOG_RUNNING_STATUSES = (
    RequestLogLifecycleStatus.CONNECTING.value,
    RequestLogLifecycleStatus.STREAMING.value,
)
REQUEST_LOG_HEALTH_STATUSES = (
    RequestLogLifecycleStatus.SUCCEEDED.value,
    RequestLogLifecycleStatus.FAILED.value,
)
REQUEST_LOG_TERMINAL_STATUSES = (
    *REQUEST_LOG_HEALTH_STATUSES,
    RequestLogLifecycleStatus.CANCELLED.value,
)
REQUEST_LOG_MODEL_FAMILY_PREFIXES: dict[str, tuple[str, ...]] = {
    "openai": ("gpt-", "o1", "o3", "o4", "chatgpt", "openai", "text-embedding"),
    "claude": ("claude", "anthropic"),
    "gemini": ("gemini", "gemma", "google"),
    "deepseek": ("deepseek",),
    "qwen": ("qwen", "qwq", "alibaba"),
    "kimi": ("moonshot", "kimi"),
    "glm": ("glm", "chatglm", "zhipu", "z-ai", "zai-"),
    "minimax": ("minimax", "abab", "minmax"),
}
