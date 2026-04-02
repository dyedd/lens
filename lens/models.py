from __future__ import annotations

from enum import Enum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class ProtocolKind(str, Enum):
    OPENAI_CHAT = "openai_chat"
    OPENAI_RESPONSES = "openai_responses"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class ProviderStatus(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class ProviderUrlItem(BaseModel):
    url: HttpUrl
    delay: int = Field(default=0, ge=0)


class ProviderKeyItem(BaseModel):
    key: str = Field(min_length=1)
    remark: str = ""
    enabled: bool = True


class RoutingStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    FAILOVER = "failover"


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    protocol: ProtocolKind
    base_url: HttpUrl
    api_key: str = Field(min_length=1)
    status: ProviderStatus = ProviderStatus.ENABLED
    headers: dict[str, str] = Field(default_factory=dict)
    model_patterns: list[str] = Field(default_factory=list)
    base_urls: list[ProviderUrlItem] = Field(default_factory=list)
    keys: list[ProviderKeyItem] = Field(default_factory=list)
    proxy: bool = False
    channel_proxy: str = ""
    param_override: str = ""
    match_regex: str = ""


class ProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    protocol: ProtocolKind
    base_url: HttpUrl
    api_key: str = Field(min_length=1)
    status: ProviderStatus = ProviderStatus.ENABLED
    headers: dict[str, str] = Field(default_factory=dict)
    model_patterns: list[str] = Field(default_factory=list)
    base_urls: list[ProviderUrlItem] = Field(default_factory=list)
    keys: list[ProviderKeyItem] = Field(default_factory=list)
    proxy: bool = False
    channel_proxy: str = ""
    param_override: str = ""
    match_regex: str = ""

    @field_validator("model_patterns")
    @classmethod
    def validate_model_patterns(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"Invalid regex pattern: {pattern}. {exc}") from exc
        return patterns


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: ProtocolKind | None = None
    name: str | None = None
    base_url: HttpUrl | None = None
    api_key: str | None = Field(default=None, min_length=1)
    status: ProviderStatus | None = None
    headers: dict[str, str] | None = None
    model_patterns: list[str] | None = None
    base_urls: list[ProviderUrlItem] | None = None
    keys: list[ProviderKeyItem] | None = None
    proxy: bool | None = None
    channel_proxy: str | None = None
    param_override: str | None = None
    match_regex: str | None = None

    @field_validator("model_patterns")
    @classmethod
    def validate_model_patterns(cls, patterns: list[str] | None) -> list[str] | None:
        if patterns is None:
            return None
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"Invalid regex pattern: {pattern}. {exc}") from exc
        return patterns


class ProviderModelFetchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: ProtocolKind
    base_url: HttpUrl | None = None
    api_key: str | None = Field(default=None, min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    base_urls: list[ProviderUrlItem] = Field(default_factory=list)
    keys: list[ProviderKeyItem] = Field(default_factory=list)
    channel_proxy: str = ""
    match_regex: str = ""

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


class ProviderHealth(BaseModel):
    provider_id: str
    consecutive_failures: int = 0
    last_error: str | None = None


class RouteState(BaseModel):
    protocol: ProtocolKind
    next_index: int = 0
    provider_ids: list[str] = Field(default_factory=list)
    requested_model: str | None = None


class RoutePreview(BaseModel):
    protocol: ProtocolKind
    requested_model: str | None = None
    matched_group_name: str | None = None
    strategy: RoutingStrategy | None = None
    matched_provider_ids: list[str] = Field(default_factory=list)
    items: list["RoutePreviewItem"] = Field(default_factory=list)


class RoutePreviewItem(BaseModel):
    provider_id: str
    provider_name: str = ""
    model_name: str | None = None


class RoutePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: ProtocolKind
    model: str | None = None


class RouterSnapshot(BaseModel):
    routes: list[RouteState]
    health: list[ProviderHealth]


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
    first_token_timeout: int = Field(default=0, ge=0)
    session_keep_time: int = Field(default=0, ge=0)
    items: list["ModelGroupItem"] = Field(default_factory=list)


class ModelGroupItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    provider_name: str = ""
    model_name: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)


class ModelGroupItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    enabled: bool = True


class ModelGroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    protocol: ProtocolKind
    strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN
    match_regex: str = ""
    first_token_timeout: int = Field(default=0, ge=0)
    session_keep_time: int = Field(default=0, ge=0)
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
    first_token_timeout: int | None = Field(default=None, ge=0)
    session_keep_time: int | None = Field(default=None, ge=0)
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

    provider_id: str
    provider_name: str
    base_url: str
    model_name: str


class ModelGroupCandidatesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: ProtocolKind | None = None
    name: str = ""
    match_regex: str = ""
    exclude_items: list[ModelGroupItemInput] = Field(default_factory=list)

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


class ModelGroupCandidatesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[ModelGroupCandidateItem] = Field(default_factory=list)
    matched_items: list[ModelGroupCandidateItem] = Field(default_factory=list)


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
    provider_id: str | None = None
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
    enabled_providers: int = 0


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
