from typing import Literal

from pydantic import AwareDatetime, Field, HttpUrl, field_validator

from ..core.urls import canonicalize_base_url
from .model_groups import ModelGroupReconcileReport
from .protocols import (
    ChannelModelSyncStatus,
    ChannelProxyMode,
    ChannelStatus,
    ProtocolKind,
)
from .upstream_rules import HeaderRule, ParamOverrideRule
from .validation import ContextWindow, StrictBaseModel


class ChannelKeyItem(StrictBaseModel):
    id: str = ""
    key: str = Field(min_length=1)
    remark: str = ""
    number: int = Field(default=0, ge=0)
    rate_source: Literal["none", "sub2api", "newapi"] = "none"
    rate_multiplier: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class ChannelDiscoveredModel(StrictBaseModel):
    id: str = ""
    credential_id: str = ""
    credential_name: str = ""
    model_name: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)
    context_window: ContextWindow | None = None
    upstream_context_window: ContextWindow | None = None
    catalog_context_window: ContextWindow | None = None


class ChannelConfig(StrictBaseModel):
    id: str
    site_id: str = ""
    site_tags: list[str] = Field(default_factory=list)
    name: str
    protocol: ProtocolKind
    base_url: HttpUrl
    endpoint_kind: Literal[
        "default",
        "openai_chat",
        "openai_responses",
        "openai_embedding",
        "openai_image",
        "anthropic",
        "gemini",
        "rerank",
        "models",
        "china",
        "protocol",
    ] = "default"
    model_list_url: HttpUrl | None = None
    api_key: str = Field(min_length=1)
    status: ChannelStatus = ChannelStatus.ENABLED
    headers: list[HeaderRule] = Field(default_factory=list)
    model_patterns: list[str] = Field(default_factory=list)
    keys: list[ChannelKeyItem] = Field(default_factory=list)
    models: list[ChannelDiscoveredModel] = Field(default_factory=list)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
    _canonicalize_base_url = field_validator("base_url", mode="before")(
        canonicalize_base_url
    )


class ChannelModelSyncRequest(StrictBaseModel):
    site_ids: list[str] | None = None
    credential_ids: list[str] | None = None


class ChannelModelSyncResultItem(StrictBaseModel):
    site_id: str
    site_name: str
    protocol_config_id: str
    credential_id: str
    credential_name: str
    status: ChannelModelSyncStatus
    error: str = ""
    added: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    restored: list[str] = Field(default_factory=list)


class ChannelModelSyncResponse(StrictBaseModel):
    """One model sync run: per-credential catalog changes, then group changes."""

    id: str = ""
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    items: list[ChannelModelSyncResultItem] = Field(default_factory=list)
    groups: ModelGroupReconcileReport = Field(default_factory=ModelGroupReconcileReport)
