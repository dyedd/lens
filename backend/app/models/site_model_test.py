from pydantic import Field, HttpUrl, field_validator

from ..core.urls import canonicalize_base_url
from .protocols import ChannelProxyMode, ProtocolKind
from .sites import (
    SiteBaseUrlKind,
    SiteCredentialInput,
    canonicalize_text_list,
    require_non_empty_text,
)
from .upstream_rules import HeaderRule, ParamOverrideRule
from .validation import ContextWindow, StrictBaseModel


class SiteModelFetchRequest(StrictBaseModel):
    base_url: HttpUrl
    # Omitted: try each listing protocol until the upstream answers.
    protocol: ProtocolKind | None = None
    headers: list[HeaderRule] = Field(default_factory=list)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    credentials: list[SiteCredentialInput] = Field(default_factory=list, max_length=20)
    credential_ids: list[str] = Field(default_factory=list, max_length=20)

    _canonicalize_base_url = field_validator("base_url", mode="before")(
        canonicalize_base_url
    )


class SiteModelFetchItem(StrictBaseModel):
    credential_id: str
    credential_name: str = ""
    model_name: str
    # Size this upstream reports for the deployment being discovered.
    context_window: ContextWindow | None = None
    # Size the shared catalog publishes for the model name; display-only.
    catalog_context_window: ContextWindow | None = None


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
        require_non_empty_text
    )


class SiteModelProtocolDetectionRequest(StrictBaseModel):
    base_url: HttpUrl
    endpoint_kind: SiteBaseUrlKind = "default"
    headers: list[HeaderRule] = Field(default_factory=list)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
    credential: SiteModelTestCredential
    model_names: list[str] = Field(min_length=1, max_length=50)

    _canonicalize_base_url = field_validator("base_url", mode="before")(
        canonicalize_base_url
    )
    _canonicalize_model_names = field_validator("model_names")(canonicalize_text_list)


class SiteModelProtocolDetectionResult(StrictBaseModel):
    model_name: str
    # None when no protocol answered; the error says why.
    protocol: ProtocolKind | None = None
    error_message: str = ""


class SiteModelTestResult(StrictBaseModel):
    success: bool
    status_code: int | None = None
    latency_ms: int = Field(default=0, ge=0)
    model_name: str
    credential_id: str
    output_text: str = ""
    error_message: str = ""
    debug: dict[str, dict[str, object]] | None = None
