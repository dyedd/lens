from enum import Enum
import json
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def normalize_base_url(value: Any) -> Any:
    text = str(value).strip()
    parsed = urlsplit(text)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1beta"):
        path = path[:-7]
    elif path.endswith("/v1"):
        path = path[:-3]
    rebuilt = urlunsplit(
        (parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)
    )
    before_fragment, fragment_separator, _ = text.partition("#")
    has_empty_query = "?" in before_fragment and parsed.query == ""
    has_empty_fragment = bool(fragment_separator) and parsed.fragment == ""
    if has_empty_query:
        if "#" in rebuilt:
            rebuilt = rebuilt.replace("#", "?#", 1)
        else:
            rebuilt += "?"
    if has_empty_fragment and "#" not in rebuilt:
        rebuilt += "#"
    return rebuilt


def _validate_regex_pattern(pattern: str) -> str:
    if not pattern:
        return pattern
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid regex pattern: {pattern}. {exc}") from exc
    return pattern


def _normalize_weekdays_list(value: list[int]) -> list[int]:
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


def _validate_cronjob_schedule(
    schedule_type: "CronjobScheduleType | None",
    run_at_time: str | None,
    weekdays: list[int] | None,
) -> None:
    if schedule_type == CronjobScheduleType.DAILY and not run_at_time:
        raise ValueError("Daily cron jobs require run_at_time")
    if schedule_type == CronjobScheduleType.WEEKLY:
        if not run_at_time:
            raise ValueError("Weekly cron jobs require run_at_time")
        if not weekdays:
            raise ValueError("Weekly cron jobs require weekdays")


class ProtocolKind(str, Enum):
    OPENAI_CHAT = "openai_chat"
    OPENAI_RESPONSES = "openai_responses"
    OPENAI_EMBEDDING = "openai_embedding"
    OPENAI_IMAGE = "openai_image"
    RERANK = "rerank"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class ChannelProxyMode(str, Enum):
    INHERIT = "inherit"
    DIRECT = "direct"
    CUSTOM = "custom"


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


class RoutingStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    FAILOVER = "failover"


class ModelGroupSyncFilterMode(str, Enum):
    NONE = ""
    CONTAINS = "contains"
    REGEX = "regex"


class UpstreamHeaderRuleMatchType(str, Enum):
    EXACT = "exact"
    REGEX = "regex"


class UpstreamParamOverrideRuleMatchType(str, Enum):
    EXACT = "exact"
    REGEX = "regex"


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


class ChannelKeyItem(StrictBaseModel):
    id: str = ""
    key: str = Field(min_length=1)
    remark: str = ""
    enabled: bool = True


class ChannelDiscoveredModel(StrictBaseModel):
    id: str = ""
    credential_id: str = ""
    credential_name: str = ""
    model_name: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)


class ChannelConfig(StrictBaseModel):
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
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: str = ""
    match_regex: str = ""

    _normalize_base_url = field_validator("base_url", mode="before")(normalize_base_url)


class SiteBaseUrl(StrictBaseModel):
    id: str
    url: HttpUrl
    name: str = ""
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)
    supported_protocols: list[ProtocolKind] = Field(default_factory=list)

    _normalize_url = field_validator("url", mode="before")(normalize_base_url)


class SiteBaseUrlInput(StrictBaseModel):
    id: str | None = None
    url: HttpUrl
    name: str = ""
    enabled: bool = True
    supported_protocols: list[ProtocolKind] = Field(default_factory=list)

    _normalize_url = field_validator("url", mode="before")(normalize_base_url)


class SiteCredential(StrictBaseModel):
    id: str
    name: str
    api_key: str = Field(min_length=1)
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)


class SiteCredentialInput(StrictBaseModel):
    id: str | None = None
    name: str
    api_key: str = Field(min_length=1)
    enabled: bool = True


class SiteModel(StrictBaseModel):
    id: str
    credential_id: str
    credential_name: str = ""
    model_name: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)
    protocol: ProtocolKind | None = None


class SiteModelInput(StrictBaseModel):
    id: str | None = None
    credential_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    enabled: bool = True
    protocol: ProtocolKind


class SiteProtocolConfig(StrictBaseModel):
    id: str
    name: str = ""
    protocols: list[ProtocolKind] = Field(default_factory=list)
    enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: str = ""
    match_regex: str = ""
    base_url_id: str = Field(min_length=1)
    credential_id: str = ""
    models: list[SiteModel] = Field(default_factory=list)


class SiteProtocolConfigInput(StrictBaseModel):
    id: str | None = None
    name: str = ""
    protocols: list[ProtocolKind] = Field(default_factory=list)
    enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: str = ""
    match_regex: str = ""
    base_url_id: str = Field(min_length=1)
    credential_id: str = ""
    models: list[SiteModelInput] = Field(default_factory=list)

    @field_validator("match_regex")
    @classmethod
    def validate_match_regex(cls, pattern: str) -> str:
        return _validate_regex_pattern(pattern)


class SiteConfig(StrictBaseModel):
    id: str
    name: str
    base_urls: list[SiteBaseUrl] = Field(default_factory=list)
    credentials: list[SiteCredential] = Field(default_factory=list)
    protocols: list[SiteProtocolConfig] = Field(default_factory=list)


class SiteRuntimeSummary(StrictBaseModel):
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


class SiteChannelRuntimeSummary(StrictBaseModel):
    channel_id: str
    health_buckets: list["SiteChannelHealthBucket"] = Field(default_factory=list)


class SiteChannelHealthBucket(StrictBaseModel):
    started_at: str
    ended_at: str
    success_count: int = 0
    total_count: int = 0


class SiteCreate(StrictBaseModel):
    name: str
    base_urls: list[SiteBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    protocols: list[SiteProtocolConfigInput] = Field(default_factory=list)


class SiteUpdate(StrictBaseModel):
    name: str
    base_urls: list[SiteBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    protocols: list[SiteProtocolConfigInput] = Field(default_factory=list)


class SiteImportBaseUrlInput(StrictBaseModel):
    ref: str = ""
    url: HttpUrl
    name: str = ""
    enabled: bool = True

    _normalize_url = field_validator("url", mode="before")(normalize_base_url)


class SiteImportCredentialInput(StrictBaseModel):
    ref: str = ""
    name: str = ""
    api_key: str = Field(min_length=1)
    enabled: bool = True


class SiteImportModelInput(StrictBaseModel):
    model_name: str = Field(min_length=1)
    credential_ref: str = ""
    enabled: bool = True


class SiteImportProtocolInput(StrictBaseModel):
    protocol: ProtocolKind
    enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: str = ""
    match_regex: str = ""
    base_url_ref: str = ""
    credential_ref: str = ""
    models: list[SiteImportModelInput] = Field(default_factory=list)

    @field_validator("match_regex")
    @classmethod
    def validate_match_regex(cls, pattern: str) -> str:
        return _validate_regex_pattern(pattern)


class SiteImportItem(StrictBaseModel):
    name: str
    base_urls: list[SiteImportBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteImportCredentialInput] = Field(default_factory=list)
    protocols: list[SiteImportProtocolInput] = Field(default_factory=list)


class SiteBatchImportRequest(StrictBaseModel):
    sites: list[SiteImportItem] = Field(default_factory=list)


class SiteBatchImportSkipped(StrictBaseModel):
    index: int = Field(ge=0)
    name: str
    reason: str


class SiteBatchImportError(StrictBaseModel):
    index: int = Field(ge=0)
    field: str
    message: str


class SiteBatchImportResult(StrictBaseModel):
    committed: bool = False
    created_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    created: list[SiteConfig] = Field(default_factory=list)
    skipped: list[SiteBatchImportSkipped] = Field(default_factory=list)
    errors: list[SiteBatchImportError] = Field(default_factory=list)


class SiteModelFetchRequest(StrictBaseModel):
    base_url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    match_regex: str = ""
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    credential_id: str = Field(min_length=1)

    _normalize_base_url = field_validator("base_url", mode="before")(normalize_base_url)

    @field_validator("match_regex")
    @classmethod
    def validate_match_regex(cls, pattern: str) -> str:
        return _validate_regex_pattern(pattern)


class SiteModelFetchItem(StrictBaseModel):
    credential_id: str
    credential_name: str = ""
    model_name: str


class SiteModelTestCredential(StrictBaseModel):
    id: str = Field(min_length=1)
    name: str = ""
    api_key: str = Field(min_length=1)


class SiteModelTestRequest(StrictBaseModel):
    protocol: ProtocolKind
    base_url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: str = ""
    credential: SiteModelTestCredential
    model_name: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=2000)

    _normalize_base_url = field_validator("base_url", mode="before")(normalize_base_url)

    @field_validator("model_name", "prompt")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value cannot be empty")
        return normalized


class SiteModelTestResult(StrictBaseModel):
    success: bool
    status_code: int | None = None
    latency_ms: int = Field(default=0, ge=0)
    model_name: str
    credential_id: str
    output_text: str = ""
    error_message: str = ""


class ChannelKeyHealth(StrictBaseModel):
    credential_id: str
    consecutive_failures: int = 0
    cooled_until: float = 0.0
    cooldown_remaining_seconds: int = 0
    last_cooldown_seconds: int = 0
    available: bool = True


class ChannelHealth(StrictBaseModel):
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


class RouteState(StrictBaseModel):
    protocol: ProtocolKind
    next_index: int = 0
    next_channel_id: str | None = None
    channel_ids: list[str] = Field(default_factory=list)
    available_channel_ids: list[str] = Field(default_factory=list)
    cooldown_channel_ids: list[str] = Field(default_factory=list)
    requested_model: str | None = None


class RouterSnapshot(StrictBaseModel):
    routes: list[RouteState]
    health: list[ChannelHealth]


class ErrorResponse(StrictBaseModel):
    error: dict[str, Any]


class AdminLoginRequest(StrictBaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthTokenResponse(StrictBaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminProfile(StrictBaseModel):
    id: int
    username: str


class AdminPasswordChangeRequest(StrictBaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)


class AdminProfileUpdateRequest(StrictBaseModel):
    username: str = Field(min_length=1)
    current_password: str = ""
    new_password: str = ""


class AdminProfileUpdateResponse(StrictBaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    profile: AdminProfile


class PublicBranding(StrictBaseModel):
    site_name: str
    logo_url: str = ""


class AppInfo(StrictBaseModel):
    system_version: str
    site_name: str
    logo_url: str = ""
    time_zone: str
    protocol_conversions: dict[str, list[str]] = Field(default_factory=dict)


class VersionCheckResult(StrictBaseModel):
    current_version: str
    latest_version: str
    release_url: str
    has_update: bool
    checked_at: str


class ModelGroup(StrictBaseModel):
    id: str
    name: str
    protocols: list[ProtocolKind] = Field(min_length=1)
    strategy: RoutingStrategy
    route_group_id: str = ""
    route_group_name: str = ""
    sync_filter_mode: ModelGroupSyncFilterMode = ModelGroupSyncFilterMode.NONE
    sync_filter_query: str = ""
    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    cache_read_price_per_million: float = 0.0
    cache_write_price_per_million: float = 0.0
    items: list["ModelGroupItem"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_sync_filter(self) -> "ModelGroup":
        self.sync_filter_mode, self.sync_filter_query = (
            normalize_model_group_sync_filter(
                self.sync_filter_mode,
                self.sync_filter_query,
                route_group_id=self.route_group_id,
            )
        )
        return self


class ModelGroupItem(StrictBaseModel):
    channel_id: str
    channel_name: str = ""
    protocol: ProtocolKind | None = None
    credential_id: str = Field(min_length=1)
    credential_name: str = ""
    credential_number: int = Field(default=0, ge=0)
    model_name: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)


class ModelGroupItemInput(StrictBaseModel):
    channel_id: str = Field(min_length=1)
    credential_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    enabled: bool = True


class ModelGroupCreate(StrictBaseModel):
    name: str
    protocols: list[ProtocolKind] = Field(min_length=1)
    strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN
    route_group_id: str = ""
    sync_filter_mode: ModelGroupSyncFilterMode = ModelGroupSyncFilterMode.NONE
    sync_filter_query: str = ""
    items: list[ModelGroupItemInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_sync_filter(self) -> "ModelGroupCreate":
        self.sync_filter_mode, self.sync_filter_query = (
            normalize_model_group_sync_filter(
                self.sync_filter_mode,
                self.sync_filter_query,
                route_group_id=self.route_group_id,
            )
        )
        return self


class ModelGroupUpdate(StrictBaseModel):
    name: str | None = None
    protocols: list[ProtocolKind] | None = Field(default=None, min_length=1)
    strategy: RoutingStrategy | None = None
    route_group_id: str | None = None
    sync_filter_mode: ModelGroupSyncFilterMode | None = None
    sync_filter_query: str | None = None
    items: list[ModelGroupItemInput] | None = None

    @model_validator(mode="after")
    def validate_sync_filter(self) -> "ModelGroupUpdate":
        if self.sync_filter_mode is None and self.sync_filter_query is None:
            return self
        mode = (
            self.sync_filter_mode
            if self.sync_filter_mode is not None
            else ModelGroupSyncFilterMode.NONE
        )
        query = self.sync_filter_query if self.sync_filter_query is not None else ""
        self.sync_filter_mode, self.sync_filter_query = (
            normalize_model_group_sync_filter(
                mode,
                query,
                route_group_id=self.route_group_id or "",
            )
        )
        return self


def normalize_model_group_sync_filter(
    mode: ModelGroupSyncFilterMode,
    query: str,
    *,
    route_group_id: str = "",
) -> tuple[ModelGroupSyncFilterMode, str]:
    normalized_query = query.strip()
    if route_group_id.strip() or not normalized_query:
        return ModelGroupSyncFilterMode.NONE, ""
    if mode == ModelGroupSyncFilterMode.NONE:
        return ModelGroupSyncFilterMode.NONE, ""
    if mode == ModelGroupSyncFilterMode.REGEX:
        try:
            re.compile(normalized_query)
        except re.error as exc:
            raise ValueError(
                f"Invalid model group sync regex: {normalized_query}. {exc}"
            ) from exc
    return mode, normalized_query


def _normalize_header_map(headers: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    lower_to_key: dict[str, str] = {}
    for raw_key, raw_value in headers.items():
        key = str(raw_key).strip()
        if not key:
            continue
        lower_key = key.lower()
        existing_key = lower_to_key.get(lower_key)
        if existing_key is not None:
            normalized.pop(existing_key, None)
        value = str(raw_value).strip()
        lower_to_key[lower_key] = key
        normalized[key] = value
    return normalized


class UpstreamHeaderRule(StrictBaseModel):
    enabled: bool = True
    name: str = ""
    match_type: UpstreamHeaderRuleMatchType = UpstreamHeaderRuleMatchType.EXACT
    models: list[str] = Field(default_factory=list)
    pattern: str = ""
    headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("name", "pattern")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("models")
    @classmethod
    def normalize_models(cls, models: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in models:
            model = str(item).strip()
            if not model or model in seen:
                continue
            seen.add(model)
            normalized.append(model)
        return normalized

    @field_validator("headers")
    @classmethod
    def normalize_headers(cls, headers: dict[str, str]) -> dict[str, str]:
        return _normalize_header_map(headers)

    @model_validator(mode="after")
    def validate_matcher(self) -> "UpstreamHeaderRule":
        if self.match_type == UpstreamHeaderRuleMatchType.REGEX:
            if not self.pattern:
                raise ValueError("Regex upstream header rule requires pattern")
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(
                    f"Invalid upstream header rule regex: {self.pattern}. {exc}"
                ) from exc
        return self


class UpstreamHeadersConfig(StrictBaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    global_headers: dict[str, str] = Field(default_factory=dict, alias="global")
    rules: list[UpstreamHeaderRule] = Field(default_factory=list)

    @field_validator("global_headers")
    @classmethod
    def normalize_global_headers(cls, headers: dict[str, str]) -> dict[str, str]:
        return _normalize_header_map(headers)


def normalize_upstream_headers_config_json(value: str) -> str:
    raw_value = value.strip()
    if raw_value:
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            payload = {}
        config = UpstreamHeadersConfig.model_validate(payload)
    else:
        config = UpstreamHeadersConfig()
    return json.dumps(config.model_dump(mode="json", by_alias=True), ensure_ascii=True)


class UpstreamParamOverrideRule(StrictBaseModel):
    enabled: bool = True
    name: str = ""
    match_type: UpstreamParamOverrideRuleMatchType = (
        UpstreamParamOverrideRuleMatchType.EXACT
    )
    models: list[str] = Field(default_factory=list)
    pattern: str = ""
    override: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "pattern")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("models")
    @classmethod
    def normalize_models(cls, models: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in models:
            model = str(item).strip()
            if not model or model in seen:
                continue
            seen.add(model)
            normalized.append(model)
        return normalized

    @model_validator(mode="after")
    def validate_matcher(self) -> "UpstreamParamOverrideRule":
        if "model" in self.override:
            raise ValueError("model cannot be overridden")
        if self.match_type == UpstreamParamOverrideRuleMatchType.REGEX:
            if not self.pattern:
                raise ValueError("Regex upstream param override rule requires pattern")
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(
                    f"Invalid upstream param override rule regex: "
                    f"{self.pattern}. {exc}"
                ) from exc
        return self


class UpstreamParamOverrideConfig(StrictBaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    global_override: dict[str, Any] = Field(default_factory=dict, alias="global")
    rules: list[UpstreamParamOverrideRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_global_override(self) -> "UpstreamParamOverrideConfig":
        if "model" in self.global_override:
            raise ValueError("model cannot be overridden")
        return self


def normalize_upstream_param_override_config_json(value: str) -> str:
    raw_value = value.strip()
    if raw_value:
        payload = json.loads(raw_value)
        config = UpstreamParamOverrideConfig.model_validate(payload)
    else:
        config = UpstreamParamOverrideConfig()
    return json.dumps(config.model_dump(mode="json", by_alias=True), ensure_ascii=True)


class ModelGroupCandidateItem(StrictBaseModel):
    site_id: str = ""
    channel_id: str
    channel_name: str
    protocol: ProtocolKind
    credential_id: str = Field(min_length=1)
    credential_name: str = ""
    credential_number: int = Field(default=0, ge=0)
    base_url: str
    model_name: str
    protocol_config_id: str = ""
    protocols: list[ProtocolKind] = Field(default_factory=list)
    protocol_channels: dict[ProtocolKind, str] = Field(default_factory=dict)
    items: list[ModelGroupItemInput] = Field(default_factory=list)


class ModelGroupCandidatesRequest(StrictBaseModel):
    protocols: list[ProtocolKind] = Field(default_factory=list)
    exclude_items: list[ModelGroupItemInput] = Field(default_factory=list)


class ModelGroupCandidatesResponse(StrictBaseModel):
    candidates: list[ModelGroupCandidateItem] = Field(default_factory=list)


class ModelPriceItem(StrictBaseModel):
    model_key: str
    display_name: str
    protocols: list[ProtocolKind] = Field(default_factory=list)
    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    cache_read_price_per_million: float = 0.0
    cache_write_price_per_million: float = 0.0


class ModelPriceUpdate(StrictBaseModel):
    model_key: str = Field(min_length=1)
    display_name: str = ""
    input_price_per_million: float = Field(default=0.0, ge=0.0)
    output_price_per_million: float = Field(default=0.0, ge=0.0)
    cache_read_price_per_million: float = Field(default=0.0, ge=0.0)
    cache_write_price_per_million: float = Field(default=0.0, ge=0.0)


class ModelPriceListResponse(StrictBaseModel):
    items: list[ModelPriceItem] = Field(default_factory=list)
    last_synced_at: str | None = None


class CronjobItem(StrictBaseModel):
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


class CronjobUpdate(StrictBaseModel):
    enabled: bool | None = None
    schedule_type: CronjobScheduleType | None = None
    interval_hours: int | None = Field(default=None, ge=1)
    run_at_time: str | None = Field(
        default=None, pattern=r"^([01]\d|2[0-3]):([0-5]\d)$"
    )
    weekdays: list[int] | None = None

    @field_validator("weekdays")
    @classmethod
    def normalize_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        return _normalize_weekdays_list(value)

    @model_validator(mode="after")
    def validate_schedule(self) -> "CronjobUpdate":
        _validate_cronjob_schedule(self.schedule_type, self.run_at_time, self.weekdays)
        return self


class CronjobRunResult(StrictBaseModel):
    cronjob: CronjobItem


class SettingItem(StrictBaseModel):
    key: str
    value: str


class GatewayApiKeyBase(StrictBaseModel):
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


class SettingsUpdate(StrictBaseModel):
    items: list[SettingItem]


class RequestLogItem(StrictBaseModel):
    id: int
    protocol: ProtocolKind
    user_agent: str = ""
    requested_group_name: str | None = None
    resolved_group_name: str | None = None
    upstream_model_name: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    credential_id: str | None = None
    credential_name: str = ""
    channel_has_multiple_credentials: bool = False
    gateway_key_id: str | None = None
    gateway_key_remark: str | None = None
    gateway_has_multiple_keys: bool = False
    reasoning_effort: str | None = None
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


class RequestLogAttempt(StrictBaseModel):
    channel_id: str
    channel_name: str
    credential_id: str | None = None
    credential_name: str = ""
    model_name: str | None = None
    status_code: int | None = None
    success: bool
    duration_ms: int = 0
    error_message: str | None = None
    reasoning_effort: str | None = None


class RequestLogDetail(RequestLogItem):
    request_content: str | None = None
    response_content: str | None = None
    attempts: list[RequestLogAttempt] = Field(default_factory=list)


class RequestLogFilterOption(StrictBaseModel):
    id: str
    label: str


class RequestLogPage(StrictBaseModel):
    items: list[RequestLogItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 0
    offset: int = 0
    channels: list[RequestLogFilterOption] = Field(default_factory=list)
    gateway_keys: list[RequestLogFilterOption] = Field(default_factory=list)
    gateway_has_multiple_keys: bool = False
    model_names: list[str] = Field(default_factory=list)


class ConfigBackupImportedStatsTotal(StrictBaseModel):
    input_token: int = 0
    output_token: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    wait_time: int = 0
    request_success: int = 0
    request_failed: int = 0


class ConfigBackupImportedStatsDaily(StrictBaseModel):
    date: str
    input_token: int = 0
    output_token: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    wait_time: int = 0
    request_success: int = 0
    request_failed: int = 0


class ConfigBackupRequestLogDailyStat(StrictBaseModel):
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


class ConfigBackupOverviewModelDailyStat(StrictBaseModel):
    date: str
    model: str
    requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0


class ConfigBackupStatsSnapshot(StrictBaseModel):
    imported_total: ConfigBackupImportedStatsTotal | None = None
    imported_daily: list[ConfigBackupImportedStatsDaily] = Field(default_factory=list)
    request_daily: list[ConfigBackupRequestLogDailyStat] = Field(default_factory=list)
    model_daily: list[ConfigBackupOverviewModelDailyStat] = Field(default_factory=list)


class ConfigBackupGatewayApiKey(GatewayApiKeyBase):
    id: str
    api_key: str
    spent_cost_usd: float = 0.0
    created_at: str | None = None
    updated_at: str | None = None


class ConfigBackupCronjob(StrictBaseModel):
    id: str
    enabled: bool = True
    schedule_type: CronjobScheduleType = CronjobScheduleType.INTERVAL
    interval_hours: int = Field(default=1, ge=1)
    run_at_time: str | None = Field(
        default=None, pattern=r"^([01]\d|2[0-3]):([0-5]\d)$"
    )
    weekdays: list[int] = Field(default_factory=list)

    @field_validator("weekdays")
    @classmethod
    def normalize_weekdays(cls, value: list[int]) -> list[int]:
        return _normalize_weekdays_list(value)

    @model_validator(mode="after")
    def validate_schedule(self) -> "ConfigBackupCronjob":
        _validate_cronjob_schedule(self.schedule_type, self.run_at_time, self.weekdays)
        return self


class ConfigBackupRequestLog(StrictBaseModel):
    protocol: ProtocolKind
    user_agent: str = ""
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


class ConfigBackupDump(StrictBaseModel):
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


class ConfigImportResult(StrictBaseModel):
    rows_affected: dict[str, int] = Field(default_factory=dict)


class OverviewSummaryMetric(StrictBaseModel):
    value: float
    delta: float = 0.0


class OverviewSummary(StrictBaseModel):
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


class OverviewDailyPoint(StrictBaseModel):
    date: str
    request_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    wait_time_ms: int = 0
    successful_requests: int = 0
    failed_requests: int = 0


class OverviewModelMetricPoint(StrictBaseModel):
    model: str
    requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0


class OverviewModelTrendPoint(StrictBaseModel):
    date: str
    model: str
    value: float


class OverviewModelAnalytics(StrictBaseModel):
    distribution: list[OverviewModelMetricPoint] = Field(default_factory=list)
    trend: list[OverviewModelTrendPoint] = Field(default_factory=list)
    available_models: list[str] = Field(default_factory=list)


__all__ = [
    "StrictBaseModel",
    "normalize_base_url",
    "ProtocolKind",
    "ChannelProxyMode",
    "RequestLogStatusFilter",
    "RequestLogLifecycleStatus",
    "RequestLogSortMode",
    "ChannelStatus",
    "RoutingStrategy",
    "ModelGroupSyncFilterMode",
    "UpstreamHeaderRuleMatchType",
    "UpstreamParamOverrideRuleMatchType",
    "CronjobStatus",
    "CronjobScheduleType",
    "ChannelKeyItem",
    "ChannelDiscoveredModel",
    "ChannelConfig",
    "SiteBaseUrl",
    "SiteBaseUrlInput",
    "SiteCredential",
    "SiteCredentialInput",
    "SiteModel",
    "SiteModelInput",
    "SiteProtocolConfig",
    "SiteProtocolConfigInput",
    "SiteConfig",
    "SiteRuntimeSummary",
    "SiteChannelRuntimeSummary",
    "SiteChannelHealthBucket",
    "SiteCreate",
    "SiteUpdate",
    "SiteImportBaseUrlInput",
    "SiteImportCredentialInput",
    "SiteImportModelInput",
    "SiteImportProtocolInput",
    "SiteImportItem",
    "SiteBatchImportRequest",
    "SiteBatchImportSkipped",
    "SiteBatchImportError",
    "SiteBatchImportResult",
    "SiteModelFetchRequest",
    "SiteModelFetchItem",
    "SiteModelTestCredential",
    "SiteModelTestRequest",
    "SiteModelTestResult",
    "ChannelKeyHealth",
    "ChannelHealth",
    "RouteState",
    "RouterSnapshot",
    "ErrorResponse",
    "AdminLoginRequest",
    "AuthTokenResponse",
    "AdminProfile",
    "AdminPasswordChangeRequest",
    "AdminProfileUpdateRequest",
    "AdminProfileUpdateResponse",
    "PublicBranding",
    "AppInfo",
    "VersionCheckResult",
    "ModelGroup",
    "ModelGroupItem",
    "ModelGroupItemInput",
    "ModelGroupCreate",
    "ModelGroupUpdate",
    "normalize_model_group_sync_filter",
    "UpstreamHeaderRule",
    "UpstreamHeadersConfig",
    "normalize_upstream_headers_config_json",
    "UpstreamParamOverrideRule",
    "UpstreamParamOverrideConfig",
    "normalize_upstream_param_override_config_json",
    "ModelGroupCandidateItem",
    "ModelGroupCandidatesRequest",
    "ModelGroupCandidatesResponse",
    "ModelPriceItem",
    "ModelPriceUpdate",
    "ModelPriceListResponse",
    "CronjobItem",
    "CronjobUpdate",
    "CronjobRunResult",
    "SettingItem",
    "GatewayApiKeyBase",
    "GatewayApiKeyCreate",
    "GatewayApiKeyUpdate",
    "GatewayApiKey",
    "SettingsUpdate",
    "ConfigBackupImportedStatsTotal",
    "ConfigBackupImportedStatsDaily",
    "ConfigBackupRequestLogDailyStat",
    "ConfigBackupOverviewModelDailyStat",
    "ConfigBackupStatsSnapshot",
    "ConfigBackupGatewayApiKey",
    "ConfigBackupCronjob",
    "ConfigBackupRequestLog",
    "ConfigBackupDump",
    "ConfigImportResult",
    "RequestLogItem",
    "RequestLogAttempt",
    "RequestLogDetail",
    "RequestLogFilterOption",
    "RequestLogPage",
    "OverviewSummaryMetric",
    "OverviewSummary",
    "OverviewDailyPoint",
    "OverviewModelMetricPoint",
    "OverviewModelTrendPoint",
    "OverviewModelAnalytics",
]
