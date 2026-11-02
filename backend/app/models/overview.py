from typing import Literal

from pydantic import Field

from .validation import StrictBaseModel


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


class OverviewAttributionItem(StrictBaseModel):
    key: str
    label: str
    is_deleted: bool = False
    requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    wait_time_ms: int = 0
    cache_hit_rate: float | None = None


class OverviewAttributionTrendPoint(StrictBaseModel):
    date: str
    key: str
    value: float | None = None


class OverviewAttributionFilterOption(StrictBaseModel):
    key: str
    label: str
    is_deleted: bool = False


class OverviewAttributionCoverage(StrictBaseModel):
    has_dimension_history: bool = False
    has_hourly_history: bool = False


class OverviewAttribution(StrictBaseModel):
    items: list[OverviewAttributionItem] = Field(default_factory=list)
    trend: list[OverviewAttributionTrendPoint] = Field(default_factory=list)
    filters: list[OverviewAttributionFilterOption] = Field(default_factory=list)
    dimension: Literal["model", "channel", "agent"]
    metric: Literal["requests", "tokens", "cost", "cache", "duration"]
    filter_key: str | None = None
    filter_label: str | None = None
    coverage: OverviewAttributionCoverage = Field(
        default_factory=OverviewAttributionCoverage
    )
