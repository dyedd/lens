from pydantic import Field

from .common import StrictBaseModel
from .protocols import ProtocolKind, RequestLogLifecycleStatus


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
    credential_number: int = Field(default=0, ge=0)
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
    credential_number: int = Field(default=0, ge=0)
    channel_has_multiple_credentials: bool = False
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
