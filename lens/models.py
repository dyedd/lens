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
    model_name: str | None = None
    status: ProviderStatus = ProviderStatus.ENABLED
    weight: int = Field(default=1, ge=1)
    priority: int = Field(default=100, ge=1)
    headers: dict[str, str] = Field(default_factory=dict)
    model_patterns: list[str] = Field(default_factory=list)


class ProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    protocol: ProtocolKind
    base_url: HttpUrl
    api_key: str = Field(min_length=1)
    model_name: str | None = None
    status: ProviderStatus = ProviderStatus.ENABLED
    weight: int = Field(default=1, ge=1)
    priority: int = Field(default=100, ge=1)
    headers: dict[str, str] = Field(default_factory=dict)
    model_patterns: list[str] = Field(default_factory=list)

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

    name: str | None = None
    base_url: HttpUrl | None = None
    api_key: str | None = Field(default=None, min_length=1)
    model_name: str | None = None
    status: ProviderStatus | None = None
    weight: int | None = Field(default=None, ge=1)
    priority: int | None = Field(default=None, ge=1)
    headers: dict[str, str] | None = None
    model_patterns: list[str] | None = None

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
    provider_ids: list[str] = Field(default_factory=list)
    enabled: bool = True


class ModelGroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    protocol: ProtocolKind
    strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN
    provider_ids: list[str] = Field(default_factory=list)
    enabled: bool = True


class ModelGroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    protocol: ProtocolKind | None = None
    strategy: RoutingStrategy | None = None
    provider_ids: list[str] | None = None
    enabled: bool | None = None


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
