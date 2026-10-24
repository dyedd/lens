from typing import Literal

from pydantic import Field, HttpUrl, field_validator

from ..core.urls import canonicalize_base_url
from .protocols import ChannelProxyMode, ProtocolKind
from .sites import (
    SiteBaseUrlKind,
    SiteConfig,
    SiteTags,
    canonicalize_text_list,
    require_non_empty_text,
)
from .upstream_rules import HeaderRule, ParamOverrideRule
from .validation import StrictBaseModel


class SiteImportBaseUrlInput(StrictBaseModel):
    ref: str
    url: HttpUrl
    kind: SiteBaseUrlKind = "default"

    _require_non_empty_ref = field_validator("ref")(require_non_empty_text)
    _canonicalize_url = field_validator("url", mode="before")(canonicalize_base_url)


class SiteImportCredentialInput(StrictBaseModel):
    ref: str
    name: str = ""
    api_key: str = Field(min_length=1)
    base_url_ref: str = ""

    _require_non_empty_ref = field_validator("ref")(require_non_empty_text)


class SiteImportModelInput(StrictBaseModel):
    model_name: str = Field(min_length=1)
    credential_ref: str = Field(min_length=1)
    protocol: ProtocolKind | None = None
    enabled: bool = True

    @field_validator("protocol", mode="before")
    @classmethod
    def _normalize_legacy_protocol(cls, value: object) -> object:
        return ProtocolKind.OPENAI_CHAT if value == "auto" else value


class SiteImportProtocolInput(StrictBaseModel):
    protocol: ProtocolKind = ProtocolKind.OPENAI_CHAT
    base_url_ref: str
    credential_refs: list[str] = Field(min_length=1)
    models: list[SiteImportModelInput] = Field(default_factory=list)

    @field_validator("protocol", mode="before")
    @classmethod
    def _normalize_legacy_protocol(cls, value: object) -> object:
        return ProtocolKind.OPENAI_CHAT if value == "auto" else value

    _validate_base_url_ref = field_validator("base_url_ref")(require_non_empty_text)
    _canonicalize_credential_refs = field_validator("credential_refs")(
        canonicalize_text_list
    )


class SiteImportItem(StrictBaseModel):
    name: str
    enabled: bool
    tags: SiteTags = Field(default_factory=list)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    headers: list[HeaderRule] = Field(default_factory=list)
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
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
