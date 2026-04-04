from __future__ import annotations

from enum import Enum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def normalize_base_url(value: Any) -> Any:
    if value is None:
        return value
    text = str(value).strip().rstrip("/")
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
    base_url: HttpUrl
    credentials: list[SiteCredential] = Field(default_factory=list)
    protocols: list[SiteProtocolConfig] = Field(default_factory=list)

    _normalize_base_url = field_validator("base_url", mode="before")(normalize_base_url)


class SiteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    base_url: HttpUrl
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    protocols: list[SiteProtocolConfigInput] = Field(default_factory=list)

    _normalize_base_url = field_validator("base_url", mode="before")(normalize_base_url)


class SiteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    base_url: HttpUrl
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    protocols: list[SiteProtocolConfigInput] = Field(default_factory=list)

    _normalize_base_url = field_validator("base_url", mode="before")(normalize_base_url)


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


class ChannelHealth(BaseModel):
    channel_id: str
    consecutive_failures: int = 0
    last_error: str | None = None


class RouteState(BaseModel):
    protocol: ProtocolKind
    next_index: int = 0
    channel_ids: list[str] = Field(default_factory=list)
    requested_model: str | None = None


class RoutePreview(BaseModel):
    protocol: ProtocolKind
    requested_model: str | None = None
    matched_group_name: str | None = None
    strategy: RoutingStrategy | None = None
    matched_channel_ids: list[str] = Field(default_factory=list)
    items: list["RoutePreviewItem"] = Field(default_factory=list)


class RoutePreviewItem(BaseModel):
    channel_id: str
    channel_name: str = ""
    model_name: str | None = None


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


class ModelGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    protocol: ProtocolKind
    strategy: RoutingStrategy
    match_regex: str = ""
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
    match_regex: str = ""
    items: list[ModelGroupItemInput] = Field(default_factory=list)

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


class ModelGroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    protocol: ProtocolKind | None = None
    strategy: RoutingStrategy | None = None
    match_regex: str | None = None
    items: list[ModelGroupItemInput] | None = None

    @field_validator("match_regex")
    @classmethod
    def validate_match_regex(cls, pattern: str | None) -> str | None:
        if not pattern:
            return pattern
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid regex pattern: {pattern}. {exc}") from exc
        return pattern


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


class SettingItem(BaseModel):
    key: str
    value: str


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SettingItem]


class RequestLogItem(BaseModel):
    id: int
    protocol: ProtocolKind
    requested_model: str | None = None
    matched_group_name: str | None = None
    channel_id: str | None = None
    gateway_key_id: str | None = None
    status_code: int
    success: bool
    latency_ms: int
    resolved_model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    error_message: str | None = None
    created_at: str


class OverviewMetrics(BaseModel):
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: int = 0
    active_gateway_keys: int = 0
    enabled_groups: int = 0
    enabled_channels: int = 0


class OverviewSummaryMetric(BaseModel):
    value: float
    delta: float = 0.0


class OverviewSummary(BaseModel):
    request_count: OverviewSummaryMetric
    wait_time_ms: OverviewSummaryMetric
    total_tokens: OverviewSummaryMetric
    total_cost_usd: OverviewSummaryMetric
    input_tokens: OverviewSummaryMetric
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
