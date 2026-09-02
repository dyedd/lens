from pydantic import Field, HttpUrl, field_validator

from ..core.urls import canonicalize_base_url
from .protocols import ChannelProxyMode, ProtocolKind
from .sites import (
    SiteCredentialInput,
    _require_non_empty_text,
    _validate_match_regex,
)
from .upstream_rules import HeaderRule, ParamOverrideRule
from .validation import StrictBaseModel


class SiteModelFetchRequest(StrictBaseModel):
    base_url: HttpUrl
    headers: list[HeaderRule] = Field(default_factory=list)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    match_regex: str = ""
    credentials: list[SiteCredentialInput] = Field(default_factory=list, max_length=20)
    credential_ids: list[str] = Field(default_factory=list, max_length=20)

    _canonicalize_base_url = field_validator("base_url", mode="before")(
        canonicalize_base_url
    )

    validate_match_regex = _validate_match_regex


class SiteModelFetchItem(StrictBaseModel):
    credential_id: str
    credential_name: str = ""
    model_name: str


class SiteModelTestCredential(StrictBaseModel):
    id: str = Field(min_length=1)
    name: str = ""
    api_key: str = Field(min_length=1)


class SiteModelTestRequest(StrictBaseModel):
    protocol: ProtocolKind
    base_url: HttpUrl
    headers: list[HeaderRule] = Field(default_factory=list)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
    credential: SiteModelTestCredential
    model_name: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=2000)

    _canonicalize_base_url = field_validator("base_url", mode="before")(
        canonicalize_base_url
    )
    _require_non_empty_text = field_validator("model_name", "prompt")(
        _require_non_empty_text
    )


class SiteModelTestResult(StrictBaseModel):
    success: bool
    status_code: int | None = None
    latency_ms: int = Field(default=0, ge=0)
    model_name: str
    credential_id: str
    output_text: str = ""
    error_message: str = ""
