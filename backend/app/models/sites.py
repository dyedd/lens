import re
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, HttpUrl, field_validator, model_validator

from ..core.urls import canonicalize_base_url
from .model_groups import ModelGroupEnsureFromSiteResponse, ModelGroupEnsureModelInput
from .protocols import ChannelProxyMode, ModelSource, ProtocolKind
from .upstream_rules import HeaderRule, ParamOverrideRule
from .validation import StrictBaseModel


def require_non_empty_text(value: str) -> str:
    trimmed_text = value.strip()
    if not trimmed_text:
        raise ValueError("Value cannot be empty")
    return trimmed_text


def canonicalize_text_list(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    for value in values:
        item = require_non_empty_text(value)
        if item not in unique_values:
            unique_values.append(item)
    if not unique_values:
        raise ValueError("At least one value is required")
    return unique_values


def _canonicalize_site_tags(values: list[str]) -> list[str]:
    canonical_tags: list[str] = []
    for value in values:
        tag = value.strip()
        if not tag:
            raise ValueError("Site tags cannot be empty")
        if len(tag) > 80:
            raise ValueError("Site tags cannot exceed 80 characters")
        if tag not in canonical_tags:
            canonical_tags.append(tag)
    if len(canonical_tags) > 20:
        raise ValueError("Sites cannot have more than 20 tags")
    return canonical_tags


SiteTags = Annotated[list[str], AfterValidator(_canonicalize_site_tags)]
SiteCredentialRateSource = Literal["none", "sub2api", "newapi"]


class SiteBaseUrl(StrictBaseModel):
    id: str
    url: HttpUrl
    sort_order: int = Field(default=0, ge=0)

    _canonicalize_url = field_validator("url", mode="before")(canonicalize_base_url)


class SiteBaseUrlInput(StrictBaseModel):
    id: str | None = None
    url: HttpUrl

    _canonicalize_url = field_validator("url", mode="before")(canonicalize_base_url)


class SiteCredential(StrictBaseModel):
    id: str
    name: str
    api_key: str = Field(min_length=1)
    sort_order: int = Field(default=0, ge=0)
    base_url_id: str = ""
    rate_source: SiteCredentialRateSource = "none"
    rate_protocol_config_id: str = ""
    rate_group: str = ""
    rate_multiplier: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    rate_observed_at: str | None = None
    rate_last_synced_at: str | None = None
    rate_last_error: str = ""


class SiteCredentialInput(StrictBaseModel):
    id: str | None = None
    name: str
    api_key: str = Field(min_length=1)
    base_url_id: str = ""
    rate_source: SiteCredentialRateSource = "none"
    rate_protocol_config_id: str = ""
    rate_group: str = ""

    @model_validator(mode="after")
    def validate_rate_config(self) -> "SiteCredentialInput":
        self.base_url_id = self.base_url_id.strip()
        self.rate_protocol_config_id = self.rate_protocol_config_id.strip()
        self.rate_group = self.rate_group.strip()
        if self.rate_source == "none":
            self.rate_protocol_config_id = ""
            self.rate_group = ""
            return self
        if not self.rate_protocol_config_id:
            raise ValueError("Rate protocol config is required")
        if self.rate_source == "newapi" and not self.rate_group:
            raise ValueError("NewAPI rate group is required")
        if self.rate_source == "sub2api":
            self.rate_group = ""
        return self


class SiteModel(StrictBaseModel):
    id: str
    credential_id: str
    credential_name: str = ""
    model_name: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)
    protocol: ProtocolKind | None = None
    source: ModelSource = ModelSource.MANUAL


class SiteModelInput(StrictBaseModel):
    id: str | None = None
    credential_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    enabled: bool = True
    protocol: ProtocolKind = ProtocolKind.AUTO
    source: ModelSource = ModelSource.MANUAL


class SiteSyncTarget(StrictBaseModel):
    credential_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    protocol: ProtocolKind = ProtocolKind.AUTO


class SiteProtocolConfig(StrictBaseModel):
    id: str
    base_url_id: str = Field(min_length=1)
    protocols: list[ProtocolKind] = Field(default_factory=list)
    credential_ids: list[str] = Field(default_factory=list)
    auto_sync_supported_models: bool = False
    auto_sync_model_pattern: str = ""
    sync_targets: list[SiteSyncTarget] = Field(default_factory=list)
    models: list[SiteModel] = Field(default_factory=list)


class SiteProtocolConfigInput(StrictBaseModel):
    id: str | None = None
    base_url_id: str = Field(min_length=1)
    protocols: list[ProtocolKind] = Field(default_factory=list)
    auto_sync_supported_models: bool = False
    auto_sync_model_pattern: str = ""
    sync_targets: list[SiteSyncTarget] = Field(default_factory=list)
    models: list[SiteModelInput] = Field(default_factory=list)

    @field_validator("auto_sync_model_pattern")
    @classmethod
    def validate_auto_sync_model_pattern(cls, value: str) -> str:
        pattern = value.strip()
        if pattern:
            re.compile(pattern)
        return pattern

    @model_validator(mode="after")
    def validate_model_protocols(self) -> "SiteProtocolConfigInput":
        protocols_by_model: dict[tuple[str, str], set[ProtocolKind]] = {}
        for item in [*self.models, *self.sync_targets]:
            key = (item.credential_id, item.model_name.strip())
            protocols_by_model.setdefault(key, set()).add(item.protocol)
        if any(
            ProtocolKind.AUTO in protocols and len(protocols) > 1
            for protocols in protocols_by_model.values()
        ):
            raise ValueError(
                "Automatic forwarding cannot be combined with fixed protocols for the same model and credential"
            )
        return self


class SiteConfig(StrictBaseModel):
    id: str
    name: str
    enabled: bool
    tags: SiteTags
    updated_at: str | None = None
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    headers: list[HeaderRule] = Field(default_factory=list)
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
    base_urls: list[SiteBaseUrl] = Field(default_factory=list)
    credentials: list[SiteCredential] = Field(default_factory=list)
    protocols: list[SiteProtocolConfig] = Field(default_factory=list)


class SiteCreate(StrictBaseModel):
    name: str
    tags: SiteTags = Field(default_factory=list)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    headers: list[HeaderRule] = Field(default_factory=list)
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
    base_urls: list[SiteBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    protocols: list[SiteProtocolConfigInput] = Field(default_factory=list)


class SiteUpdate(StrictBaseModel):
    name: str
    tags: SiteTags = Field(default_factory=list)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    headers: list[HeaderRule] = Field(default_factory=list)
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
    base_urls: list[SiteBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    protocols: list[SiteProtocolConfigInput] = Field(default_factory=list)


class SiteModelGroupSaveRequest(SiteCreate):
    """Site payload plus transactional model-group save options."""

    site_id: str | None = None
    dry_run: bool = True
    models: list[ModelGroupEnsureModelInput] | None = None


class SiteModelGroupSaveResponse(StrictBaseModel):
    site: SiteConfig
    model_groups: ModelGroupEnsureFromSiteResponse


class SiteEnabledUpdate(StrictBaseModel):
    enabled: bool
