from typing import Literal

from pydantic import Field, HttpUrl, field_validator

from ..core.urls import canonicalize_base_url
from .protocols import (
    ChannelModelSyncStatus,
    ChannelProxyMode,
    ChannelStatus,
    ProtocolKind,
)
from .validation import StrictBaseModel


class ChannelKeyItem(StrictBaseModel):
    id: str = ""
    key: str = Field(min_length=1)
    remark: str = ""
    number: int = Field(default=0, ge=0)
    enabled: bool = True
    rate_source: Literal["none", "sub2api", "newapi"] = "none"
    rate_multiplier: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class ChannelDiscoveredModel(StrictBaseModel):
    id: str = ""
    credential_id: str = ""
    credential_name: str = ""
    model_name: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)


class ChannelConfig(StrictBaseModel):
    id: str
    site_id: str = ""
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
    _canonicalize_base_url = field_validator("base_url", mode="before")(
        canonicalize_base_url
    )


class ChannelModelSyncRequest(StrictBaseModel):
    dry_run: bool = True


class ChannelModelSyncGroupChange(StrictBaseModel):
    group_name: str
    model_name: str


class ChannelModelSyncResultItem(StrictBaseModel):
    site_id: str
    protocol_config_id: str
    protocol_config_name: str
    channel_name: str
    credential_id: str
    credential_name: str
    protocol: ProtocolKind
    status: ChannelModelSyncStatus
    error: str = ""
    warning: str = ""
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    group_added: list[ChannelModelSyncGroupChange] = Field(default_factory=list)


class ChannelModelSyncResponse(StrictBaseModel):
    dry_run: bool
    eligible_target_count: int = Field(default=0, ge=0)
    updated_target_count: int = Field(default=0, ge=0)
    unchanged_target_count: int = Field(default=0, ge=0)
    failed_target_count: int = Field(default=0, ge=0)
    items: list[ChannelModelSyncResultItem] = Field(default_factory=list)
