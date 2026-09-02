from typing import Literal

from pydantic import Field, HttpUrl, field_validator

from ..core.urls import canonicalize_base_url
from .protocols import ChannelProxyMode, ModelSource, ProtocolKind
from .sites import (
    SiteConfig,
    SiteTags,
    _canonicalize_text_list,
    _require_non_empty_text,
)
from .upstream_rules import HeaderRule, ParamOverrideRule
from .validation import StrictBaseModel


class SiteImportBaseUrlInput(StrictBaseModel):
    ref: str
    url: HttpUrl
    name: str = ""
    enabled: bool = True

    _require_non_empty_ref = field_validator("ref")(_require_non_empty_text)
    _canonicalize_url = field_validator("url", mode="before")(canonicalize_base_url)


class SiteImportCredentialInput(StrictBaseModel):
    ref: str
    name: str = ""
    api_key: str = Field(min_length=1)
    enabled: bool = True

    _require_non_empty_ref = field_validator("ref")(_require_non_empty_text)


class SiteImportModelInput(StrictBaseModel):
    model_name: str = Field(min_length=1)
    credential_ref: str = Field(min_length=1)
    enabled: bool = True
    source: ModelSource = ModelSource.MANUAL


class SiteImportProtocolInput(StrictBaseModel):
    name: str
    protocol: ProtocolKind
    enabled: bool = True
    headers: list[HeaderRule] = Field(default_factory=list)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
    base_url_ref: str
    credential_refs: list[str] = Field(min_length=1)
    models: list[SiteImportModelInput] = Field(default_factory=list)

    _validate_identifiers = field_validator("name", "base_url_ref")(
        _require_non_empty_text
    )
    _canonicalize_credential_refs = field_validator("credential_refs")(
        _canonicalize_text_list
    )


class SiteImportItem(StrictBaseModel):
    name: str
    enabled: bool
    tags: SiteTags = Field(default_factory=list)
    base_urls: list[SiteImportBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteImportCredentialInput] = Field(default_factory=list)
    protocols: list[SiteImportProtocolInput] = Field(default_factory=list)


class SiteBatchImportRequest(StrictBaseModel):
    sites: list[SiteImportItem] = Field(min_length=1)


class SiteBatchImportFieldError(StrictBaseModel):
    field: str
    message: str


class SiteBatchImportItemResult(StrictBaseModel):
    index: int = Field(ge=0)
    name: str
    status: Literal["created", "skipped", "error", "not_committed"]
    reason: str
    site: SiteConfig | None
    errors: list[SiteBatchImportFieldError]


class SiteBatchImportResult(StrictBaseModel):
    committed: bool
    created_count: int
    skipped_count: int
    error_count: int
    not_committed_count: int
    items: list[SiteBatchImportItemResult]
