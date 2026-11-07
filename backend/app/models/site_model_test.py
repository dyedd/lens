from typing import Any, Literal

from pydantic import Field, HttpUrl, field_validator, model_validator

from ..core.urls import canonicalize_base_url
from .credential_scopes import parse_legacy_credential_scopes
from .protocols import ChannelProxyMode, ProtocolKind
from .sites import (
    SiteBaseUrlKind,
    SiteCredentialInput,
    canonicalize_text_list,
    require_non_empty_text,
)
from .upstream_rules import HeaderRule, ParamOverrideRule
from .validation import ContextWindow, StrictBaseModel

ModelTestMode = Literal["direct", "codex", "claude"]


class SiteModelFetchRequest(StrictBaseModel):
    base_url_id: str = Field(default="preview", min_length=1)
    base_url: HttpUrl
    endpoint_kind: SiteBaseUrlKind = "default"
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

    @model_validator(mode="before")
    @classmethod
    def parse_legacy_scopes(cls, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        # 旧发现请求只有一个地址，只授权这次请求，不生成持久化的任意范围。
        converted = parse_legacy_credential_scopes(
            {
                **payload,
                "base_urls": [{"id": payload.get("base_url_id", "preview")}],
            }
        )
        return {key: value for key, value in converted.items() if key != "base_urls"}


class SiteModelFetchItem(StrictBaseModel):
    credential_id: str
    credential_name: str = ""
    model_name: str
    protocol: ProtocolKind
    context_window: ContextWindow | None = None


class ModelContextDetectionRequest(StrictBaseModel):
    model_names: list[str] = Field(min_length=1, max_length=1000)

    _canonicalize_model_names = field_validator("model_names")(canonicalize_text_list)


class SiteModelTestCredential(StrictBaseModel):
    id: str = Field(min_length=1)
    name: str = ""
    api_key: str = Field(min_length=1)
    base_url_ids: list[str] | None = None


class SiteModelTestRequest(StrictBaseModel):
    protocol: ProtocolKind
    base_url_id: str = Field(default="preview", min_length=1)
    base_url: HttpUrl
    headers: list[HeaderRule] = Field(default_factory=list)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
    credential: SiteModelTestCredential
    model_name: str = Field(min_length=1)
    test_mode: ModelTestMode = "direct"

    _canonicalize_base_url = field_validator("base_url", mode="before")(
        canonicalize_base_url
    )
    _require_non_empty_text = field_validator("model_name")(require_non_empty_text)

    @model_validator(mode="after")
    def validate_credential_address(self) -> "SiteModelTestRequest":
        scope = self.credential.base_url_ids
        if scope is not None and self.base_url_id not in scope:
            raise ValueError("Credential is not allowed for model testing")
        return self


class SiteModelProtocolDetectionRequest(StrictBaseModel):
    endpoint_kind: SiteBaseUrlKind = "default"
    model_names: list[str] = Field(min_length=1, max_length=1000)
    _canonicalize_model_names = field_validator("model_names")(canonicalize_text_list)


class SiteModelProtocolDetectionResult(StrictBaseModel):
    model_name: str
    protocols: list[ProtocolKind] = Field(default_factory=list)


class SiteModelTestResult(StrictBaseModel):
    success: bool
    status_code: int | None = None
    latency_ms: int = Field(default=0, ge=0)
    model_name: str
    credential_id: str
    output_text: str = ""
    error_message: str = ""
    debug: dict[str, dict[str, object]] | None = None
