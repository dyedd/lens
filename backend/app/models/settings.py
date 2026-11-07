from typing import TypedDict

from ..core.cooldown_rules import CompiledCooldownDetectionRule
from .upstream_rules import UpstreamHeadersConfig, UpstreamParamOverrideConfig
from .validation import StrictBaseModel


class SettingItem(StrictBaseModel):
    key: str
    value: str


class SettingsUpdate(StrictBaseModel):
    items: list[SettingItem]


class RuntimeSettings(TypedDict):
    proxy_url: str
    auth_access_token_minutes: int
    first_token_timeout_seconds: float
    stream_idle_timeout_seconds: float
    max_request_body_bytes: int
    time_zone: str
    cors_allow_origins: list[str]
    relay_log_body_enabled: bool
    relay_log_keep_enabled: bool
    relay_log_keep_period: int
    circuit_breaker_threshold: int
    circuit_breaker_failure_window_seconds: int
    circuit_breaker_timeout_threshold: int
    circuit_breaker_network_threshold: int
    circuit_breaker_cooldown: int
    circuit_breaker_auth_cooldown: int
    circuit_breaker_not_found_cooldown: int
    circuit_breaker_rate_limit_cooldown: int
    circuit_breaker_timeout_cooldown: int
    circuit_breaker_network_cooldown: int
    circuit_breaker_backoff_multiplier: float
    circuit_breaker_max_cooldown: int
    failover_cooled_wait_seconds: int
    circuit_breaker_escalate_threshold: int
    circuit_breaker_escalate_window_seconds: int
    failover_affinity_seconds: int
    health_scoring_enabled: bool
    health_window_seconds: int
    health_penalty_weight: float
    health_min_samples: int
    upstream_headers_config: UpstreamHeadersConfig
    upstream_param_override_config: UpstreamParamOverrideConfig
    cooldown_detection_rules: tuple[CompiledCooldownDetectionRule, ...]
    site_name: str
    site_logo_url: str
