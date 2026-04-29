from __future__ import annotations

from enum import Enum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


def normalize_base_url(value: Any) -> Any:
    if value is None:
        return value
    text = str(value).strip()
    if text.endswith("#"):
        text = text[:-1].rstrip()
    text = text.rstrip("/")
    if text.endswith("/v1beta"):
        text = text[:-7]
    elif text.endswith("/v1"):
        text = text[:-3]
    return text


class ProtocolKind(str, Enum):
    OPENAI_CHAT = "openai_chat"
    OPENAI_RESPONSES = "openai_responses"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class RequestLogModelSeries(str, Enum):
    ALL = "all"
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    KIMI = "kimi"
    GLM = "glm"
    MINIMAX = "minimax"
    OTHER = "other"


class RequestLogStatusFilter(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class RequestLogLifecycleStatus(str, Enum):
    CONNECTING = "connecting"
    STREAMING = "streaming"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RequestLogSortMode(str, Enum):
    LATEST = "latest"
    COST = "cost"
    LATENCY = "latency"
    TOKENS = "tokens"


class ChannelStatus(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class ChannelKeyItem(BaseModel):
    id: str = ""
    key: str = Field(min_length=1)
    remark: str = ""
    enabled: bool = True


class ChannelDiscoveredModel(BaseModel):
    id: str = ""
    credential_id: str = ""
    credential_name: str = ""
    model_name: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)


class RoutingStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    FAILOVER = "failover"


class ChannelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    protocol: ProtocolKind
    base_url: HttpUrl
    api_key: str = Field(min_length=1)
    status: ChannelStatus = ChannelStatus.ENABLED
    headers: dict[str, str] = Field(default_factory=dict)
    model_patterns: list[str] = Field(default_factory=list)
    keys: list[ChannelKeyItem] = Field(default_factory=list)
    models: list[ChannelDiscoveredModel] = Field(default_factory=list)
    channel_proxy: str = ""
    param_override: str = ""
    match_regex: str = ""

    _normalize_base_url = field_validator("base_url", mode="before")(normalize_base_url)


class SiteBaseUrl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    url: HttpUrl
    name: str = ""
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)

    _normalize_url = field_validator("url", mode="before")(normalize_base_url)


class SiteBaseUrlInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    url: HttpUrl
    name: str = ""
    enabled: bool = True

    _normalize_url = field_validator("url", mode="before")(normalize_base_url)


class SiteCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    api_key: str = Field(min_length=1)
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)


class SiteCredentialInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str
    api_key: str = Field(min_length=1)
    enabled: bool = True


class SiteProtocolCredentialBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_id: str
    credential_name: str = ""
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)


class SiteProtocolCredentialBindingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_id: str = Field(min_length=1)
    enabled: bool = True


class SiteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    credential_id: str
    credential_name: str = ""
    model_name: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)


class SiteModelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    credential_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    enabled: bool = True


class SiteProtocolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    protocol: ProtocolKind
    enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    channel_proxy: str = ""
    param_override: str = ""
    match_regex: str = ""
    base_url_id: str = ""
    bindings: list[SiteProtocolCredentialBinding] = Field(default_factory=list)
    models: list[SiteModel] = Field(default_factory=list)


class SiteProtocolConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    protocol: ProtocolKind
    enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    channel_proxy: str = ""
    param_override: str = ""
    match_regex: str = ""
    base_url_id: str = ""
    bindings: list[SiteProtocolCredentialBindingInput] = Field(default_factory=list)
    models: list[SiteModelInput] = Field(default_factory=list)

    @field_validator("match_regex")
    @classmethod
    def validate_match_regex(cls, pattern: str) -> str:
        if not pattern:
            return pattern
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid regex pattern: {pattern}. {exc}") from exc
        return pattern


class SiteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    base_urls: list[SiteBaseUrl] = Field(default_factory=list)
    credentials: list[SiteCredential] = Field(default_factory=list)
    protocols: list[SiteProtocolConfig] = Field(default_factory=list)


class SiteRuntimeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_id: str
    site_name: str
    recent_request_count: int = 0
    latest_request_at: str | None = None
    latest_success: bool | None = None
    latest_status_code: int | None = None
    latest_error_message: str | None = None
    latest_channel_id: str | None = None
    latest_channel_name: str | None = None
    channel_summaries: list["SiteChannelRuntimeSummary"] = Field(default_factory=list)


class SiteChannelRuntimeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str
    health_buckets: list["SiteChannelHealthBucket"] = Field(default_factory=list)


class SiteChannelHealthBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    started_at: str
    ended_at: str
    success_count: int = 0
    total_count: int = 0


class SiteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    base_urls: list[SiteBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    protocols: list[SiteProtocolConfigInput] = Field(default_factory=list)


class SiteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    base_urls: list[SiteBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    protocols: list[SiteProtocolConfigInput] = Field(default_factory=list)


class SiteModelFetchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: ProtocolKind
    base_url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    channel_proxy: str = ""
    match_regex: str = ""
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    bindings: list[SiteProtocolCredentialBindingInput] = Field(default_factory=list)

    _normalize_base_url = field_validator("base_url", mode="before")(normalize_base_url)

    @field_validator("match_regex")
    @classmethod
    def validate_match_regex(cls, pattern: str) -> str:
        if not pattern:
            return pattern
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid regex pattern: {pattern}. {exc}") from exc
        return pattern


class SiteModelFetchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_id: str
    credential_name: str = ""
    model_name: str


class ChannelKeyHealth(BaseModel):
    credential_id: str
    consecutive_failures: int = 0
    cooled_until: float = 0.0
    cooldown_remaining_seconds: int = 0
    last_cooldown_seconds: int = 0
    available: bool = True


class ChannelHealth(BaseModel):
    channel_id: str
    consecutive_failures: int = 0
    last_error: str | None = None
    last_error_category: str | None = None
    opened_until: float = 0.0
    cooldown_remaining_seconds: int = 0
    last_cooldown_seconds: int = 0
    score: float = 1.0
    available: bool = True
    available_key_count: int = 0
    cooled_key_count: int = 0
    key_health: list[ChannelKeyHealth] = Field(default_factory=list)


class RouteState(BaseModel):
    protocol: ProtocolKind
    next_index: int = 0
    next_channel_id: str | None = None
    channel_ids: list[str] = Field(default_factory=list)
    available_channel_ids: list[str] = Field(default_factory=list)
    cooldown_channel_ids: list[str] = Field(default_factory=list)
    requested_model: str | None = None


class RoutePreview(BaseModel):
    protocol: ProtocolKind
    requested_group_name: str | None = None
    resolved_group_name: str | None = None
    strategy: RoutingStrategy | None = None
    matched_channel_ids: list[str] = Field(default_factory=list)
    items: list["RoutePreviewItem"] = Field(default_factory=list)


class RoutePreviewItem(BaseModel):
    channel_id: str
    channel_name: str = ""
    model_name: str | None = None
    credential_id: str | None = None
    available: bool = True
    in_cooldown: bool = False
    cooldown_remaining_seconds: int = 0
    score: float = 1.0


class RoutePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: ProtocolKind
    model: str | None = None


class RouterSnapshot(BaseModel):
    routes: list[RouteState]
    health: list[ChannelHealth]


class ErrorResponse(BaseModel):
    error: dict[str, Any]


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminProfile(BaseModel):
    id: int
    username: str


class AdminPasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)


class AdminProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1)
    current_password: str = ""
    new_password: str = ""


class AdminProfileUpdateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    profile: AdminProfile


class PublicBranding(BaseModel):
    site_name: str
    logo_url: str = ""


class AppInfo(BaseModel):
    system_version: str
    site_name: str
    logo_url: str = ""
    time_zone: str


class VersionCheckResult(BaseModel):
    current_version: str
    latest_version: str
    release_url: str
    has_update: bool
    checked_at: str


class ModelGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    protocol: ProtocolKind
    strategy: RoutingStrategy
    route_group_id: str = ""
    route_group_name: str = ""
    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    cache_read_price_per_million: float = 0.0
    cache_write_price_per_million: float = 0.0
    items: list["ModelGroupItem"] = Field(default_factory=list)


class ModelGroupItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str
    channel_name: str = ""
    credential_id: str = ""
    credential_name: str = ""
    model_name: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)


class ModelGroupItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str = Field(min_length=1)
    credential_id: str = ""
    model_name: str = Field(min_length=1)
    enabled: bool = True


class ModelGroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    protocol: ProtocolKind
    strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN
    route_group_id: str = ""
    items: list[ModelGroupItemInput] = Field(default_factory=list)


class ModelGroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    protocol: ProtocolKind | None = None
    strategy: RoutingStrategy | None = None
    route_group_id: str | None = None
    items: list[ModelGroupItemInput] | None = None


class ModelGroupStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    request_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: int = 0
    last_resolved_model: str | None = None


class ModelGroupCandidateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str
    channel_name: str
    credential_id: str = ""
    credential_name: str = ""
    base_url: str
    model_name: str


class ModelGroupCandidatesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: ProtocolKind | None = None
    exclude_items: list[ModelGroupItemInput] = Field(default_factory=list)


class ModelGroupCandidatesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[ModelGroupCandidateItem] = Field(default_factory=list)


class ModelPriceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_key: str
    display_name: str
    protocols: list[ProtocolKind] = Field(default_factory=list)
    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    cache_read_price_per_million: float = 0.0
    cache_write_price_per_million: float = 0.0


class ModelPriceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_key: str = Field(min_length=1)
    display_name: str = ""
    input_price_per_million: float = Field(default=0.0, ge=0.0)
    output_price_per_million: float = Field(default=0.0, ge=0.0)
    cache_read_price_per_million: float = Field(default=0.0, ge=0.0)
    cache_write_price_per_million: float = Field(default=0.0, ge=0.0)


class ModelPriceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ModelPriceItem] = Field(default_factory=list)
    last_synced_at: str | None = None


class CronjobStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DISABLED = "disabled"


class CronjobScheduleType(str, Enum):
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"


class CronjobItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str = ""
    enabled: bool
    schedule_type: CronjobScheduleType = CronjobScheduleType.INTERVAL
    interval_hours: int
    run_at_time: str | None = None
    weekdays: list[int] = Field(default_factory=list)
    status: CronjobStatus
    last_started_at: str | None = None
    last_finished_at: str | None = None
    last_error: str | None = None
    next_run_at: str | None = None


class CronjobUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    schedule_type: CronjobScheduleType | None = None
    interval_hours: int | None = Field(default=None, ge=1)
    run_at_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    weekdays: list[int] | None = None

    @field_validator("weekdays")
    @classmethod
    def normalize_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        normalized: list[int] = []
        seen: set[int] = set()
        for item in value:
            weekday = int(item)
            if weekday < 1 or weekday > 7:
                raise ValueError("Weekday must be between 1 and 7")
            if weekday in seen:
                continue
            seen.add(weekday)
            normalized.append(weekday)
        return sorted(normalized)

    @model_validator(mode="after")
    def validate_schedule(self) -> "CronjobUpdate":
        if self.schedule_type == CronjobScheduleType.DAILY and not self.run_at_time:
            raise ValueError("Daily cron jobs require run_at_time")
        if self.schedule_type == CronjobScheduleType.WEEKLY:
            if not self.run_at_time:
                raise ValueError("Weekly cron jobs require run_at_time")
            if not self.weekdays:
                raise ValueError("Weekly cron jobs require weekdays")
        return self


class CronjobRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cronjob: CronjobItem


class SettingItem(BaseModel):
    key: str
    value: str


class GatewayApiKeyBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remark: str = ""
    enabled: bool = True
    allowed_models: list[str] = Field(default_factory=list)
    max_cost_usd: float = Field(default=0.0, ge=0.0)
    expires_at: str | None = None

    @field_validator("allowed_models")
    @classmethod
    def normalize_allowed_models(cls, models: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in models:
            value = str(item).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized


class GatewayApiKeyCreate(GatewayApiKeyBase):
    pass


class GatewayApiKeyUpdate(GatewayApiKeyBase):
    pass


class GatewayApiKey(GatewayApiKeyBase):
    id: str
    api_key: str
    spent_cost_usd: float = 0.0
    created_at: str
    updated_at: str


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SettingItem]


class ConfigBackupImportedStatsTotal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_token: int = 0
    output_token: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    wait_time: int = 0
    request_success: int = 0
    request_failed: int = 0


class ConfigBackupImportedStatsDaily(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    input_token: int = 0
    output_token: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    wait_time: int = 0
    request_success: int = 0
    request_failed: int = 0


class ConfigBackupRequestLogDailyStat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    request_count: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    wait_time_ms: int = 0
    input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0


class ConfigBackupOverviewModelDailyStat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    model: str
    requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0


class ConfigBackupStatsSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imported_total: ConfigBackupImportedStatsTotal | None = None
    imported_daily: list[ConfigBackupImportedStatsDaily] = Field(default_factory=list)
    request_daily: list[ConfigBackupRequestLogDailyStat] = Field(default_factory=list)
    model_daily: list[ConfigBackupOverviewModelDailyStat] = Field(default_factory=list)


class ConfigBackupGatewayApiKey(GatewayApiKeyBase):
    id: str
    api_key: str
    created_at: str | None = None
    updated_at: str | None = None


class ConfigBackupCronjob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    enabled: bool = True
    schedule_type: CronjobScheduleType = CronjobScheduleType.INTERVAL
    interval_hours: int = Field(default=1, ge=1)
    run_at_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    weekdays: list[int] = Field(default_factory=list)

    @field_validator("weekdays")
    @classmethod
    def normalize_weekdays(cls, value: list[int]) -> list[int]:
        normalized: list[int] = []
        seen: set[int] = set()
        for item in value:
            weekday = int(item)
            if weekday < 1 or weekday > 7:
                raise ValueError("Weekday must be between 1 and 7")
            if weekday in seen:
                continue
            seen.add(weekday)
            normalized.append(weekday)
        return sorted(normalized)

    @model_validator(mode="after")
    def validate_schedule(self) -> "ConfigBackupCronjob":
        if self.schedule_type == CronjobScheduleType.DAILY and not self.run_at_time:
            raise ValueError("Daily cron jobs require run_at_time")
        if self.schedule_type == CronjobScheduleType.WEEKLY:
            if not self.run_at_time:
                raise ValueError("Weekly cron jobs require run_at_time")
            if not self.weekdays:
                raise ValueError("Weekly cron jobs require weekdays")
        return self


class ConfigBackupRequestLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: ProtocolKind
    requested_group_name: str | None = None
    resolved_group_name: str | None = None
    upstream_model_name: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    gateway_key_id: str | None = None
    status_code: int | None = None
    success: bool
    lifecycle_status: RequestLogLifecycleStatus | None = None
    is_stream: bool = False
    first_token_latency_ms: int = 0
    latency_ms: int = 0
    input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    error_message: str | None = None
    created_at: str
    stats_archived: bool = False
    request_content: str | None = None
    response_content: str | None = None
    attempts: list["RequestLogAttempt"] = Field(default_factory=list)

    @model_validator(mode="after")
    def infer_lifecycle_status(self) -> "ConfigBackupRequestLog":
        if self.lifecycle_status is None:
            self.lifecycle_status = (
                RequestLogLifecycleStatus.SUCCEEDED
                if self.success
                else RequestLogLifecycleStatus.FAILED
            )
        return self


class ConfigBackupDump(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    exported_at: str
    lens_version: str
    include_request_logs: bool = False
    include_gateway_api_keys: bool = False
    settings: list[SettingItem] = Field(default_factory=list)
    sites: list[SiteConfig] = Field(default_factory=list)
    groups: list[ModelGroup] = Field(default_factory=list)
    model_prices: list[ModelPriceItem] = Field(default_factory=list)
    cronjobs: list[ConfigBackupCronjob] = Field(default_factory=list)
    stats: ConfigBackupStatsSnapshot = Field(default_factory=ConfigBackupStatsSnapshot)
    gateway_api_keys: list[ConfigBackupGatewayApiKey] = Field(default_factory=list)
    request_logs: list[ConfigBackupRequestLog] = Field(default_factory=list)


class ConfigImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows_affected: dict[str, int] = Field(default_factory=dict)


class RequestLogItem(BaseModel):
    id: int
    protocol: ProtocolKind
    requested_group_name: str | None = None
    resolved_group_name: str | None = None
    upstream_model_name: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    gateway_key_id: str | None = None
    gateway_key_remark: str | None = None
    status_code: int | None = None
    success: bool
    lifecycle_status: RequestLogLifecycleStatus
    is_stream: bool = False
    first_token_latency_ms: int = 0
    latency_ms: int
    input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    attempt_count: int = 0
    error_message: str | None = None
    created_at: str


class RequestLogAttempt(BaseModel):
    channel_id: str
    channel_name: str
    model_name: str | None = None
    status_code: int | None = None
    success: bool
    duration_ms: int = 0
    error_message: str | None = None


class RequestLogDetail(RequestLogItem):
    request_content: str | None = None
    response_content: str | None = None
    attempts: list[RequestLogAttempt] = Field(default_factory=list)


class RequestLogPage(BaseModel):
    items: list[RequestLogItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 0
    offset: int = 0
    channels: list[str] = Field(default_factory=list)


class OverviewMetrics(BaseModel):
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    enabled_gateway_keys: int = 0
    total_gateway_keys: int = 0
    enabled_groups: int = 0
    total_groups: int = 0
    enabled_channels: int = 0
    total_channels: int = 0


class OverviewPerformanceMetrics(BaseModel):
    avg_requests_per_minute: float = 0.0
    avg_tokens_per_minute: float = 0.0


class OverviewSummaryMetric(BaseModel):
    value: float
    delta: float = 0.0


class OverviewSummary(BaseModel):
    request_count: OverviewSummaryMetric
    wait_time_ms: OverviewSummaryMetric
    total_tokens: OverviewSummaryMetric
    total_cost_usd: OverviewSummaryMetric
    input_tokens: OverviewSummaryMetric
    cache_read_input_tokens: OverviewSummaryMetric
    cache_write_input_tokens: OverviewSummaryMetric
    input_cost_usd: OverviewSummaryMetric
    output_tokens: OverviewSummaryMetric
    output_cost_usd: OverviewSummaryMetric


class OverviewDailyPoint(BaseModel):
    date: str
    request_count: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    wait_time_ms: int = 0
    successful_requests: int = 0
    failed_requests: int = 0


class OverviewModelMetricPoint(BaseModel):
    model: str
    requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0


class OverviewModelTrendPoint(BaseModel):
    date: str
    model: str
    value: float


class OverviewModelAnalytics(BaseModel):
    distribution: list[OverviewModelMetricPoint] = Field(default_factory=list)
    request_ranking: list[OverviewModelMetricPoint] = Field(default_factory=list)
    trend: list[OverviewModelTrendPoint] = Field(default_factory=list)
    available_models: list[str] = Field(default_factory=list)


class OverviewDashboardData(BaseModel):
    summary: OverviewSummary
    performance: OverviewPerformanceMetrics
    daily: list[OverviewDailyPoint] = Field(default_factory=list)
    models: OverviewModelAnalytics
    logs: list[RequestLogItem] = Field(default_factory=list)
