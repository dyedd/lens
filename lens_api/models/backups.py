from pydantic import Field, field_validator, model_validator

from .common import StrictBaseModel
from .cronjobs import _normalize_weekdays_list, _validate_cronjob_schedule
from .gateway_keys import GatewayApiKeyBase
from .model_groups import ModelGroup
from .model_prices import ModelPriceItem
from .protocols import CronjobScheduleType, ProtocolKind, RequestLogLifecycleStatus
from .request_logs import RequestLogAttempt
from .settings import SettingItem
from .sites import SiteConfig

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
