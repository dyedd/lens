from pydantic import Field

from .common import StrictBaseModel
from .protocols import ProtocolKind


class ChannelKeyHealth(StrictBaseModel):
    credential_id: str
    consecutive_failures: int = 0
    cooled_until: float = 0.0
    cooldown_remaining_seconds: int = 0
    last_cooldown_seconds: int = 0
    available: bool = True


class ModelHealth(StrictBaseModel):
    model_name: str | None = None
    consecutive_failures: int = 0
    last_error: str | None = None
    last_error_category: str | None = None
    cooled_until: float = 0.0
    cooldown_remaining_seconds: int = 0
    last_cooldown_seconds: int = 0
    score: float = 1.0
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
    available_model_count: int = 0
    cooled_model_count: int = 0
    key_health: list[ChannelKeyHealth] = Field(default_factory=list)
    model_health: list[ModelHealth] = Field(default_factory=list)


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
