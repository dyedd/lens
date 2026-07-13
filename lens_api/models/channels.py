from pydantic import Field, HttpUrl, field_validator

from .common import StrictBaseModel, _validate_regex_pattern, normalize_base_url
from .protocols import ChannelProxyMode, ChannelStatus, ProtocolKind

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



class ChannelModelSyncRequest(StrictBaseModel):
    dry_run: bool = True


class ChannelModelSyncGroupChange(StrictBaseModel):
    group_name: str
    model_name: str


class ChannelModelSyncResultItem(StrictBaseModel):
    protocol_config_id: str
    channel_name: str
    success: bool
    error: str = ""
    warning: str = ""
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    group_added: list[ChannelModelSyncGroupChange] = Field(default_factory=list)


class ChannelModelSyncResponse(StrictBaseModel):
    dry_run: bool
    synced_channel_count: int = Field(default=0, ge=0)
    skipped_channel_count: int = Field(default=0, ge=0)
    items: list[ChannelModelSyncResultItem] = Field(default_factory=list)

