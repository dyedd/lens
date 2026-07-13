from pydantic import Field, HttpUrl, field_validator

from .common import StrictBaseModel, _validate_regex_pattern, normalize_base_url
from .protocols import ChannelProxyMode, ProtocolKind

class SiteBaseUrl(StrictBaseModel):
    id: str
    url: HttpUrl
    name: str = ""
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)
    supported_protocols: list[ProtocolKind] = Field(default_factory=list)

    _normalize_url = field_validator("url", mode="before")(normalize_base_url)


class SiteBaseUrlInput(StrictBaseModel):
    id: str | None = None
    url: HttpUrl
    name: str = ""
    enabled: bool = True
    supported_protocols: list[ProtocolKind] = Field(default_factory=list)

    _normalize_url = field_validator("url", mode="before")(normalize_base_url)


class SiteCredential(StrictBaseModel):
    id: str
    name: str
    api_key: str = Field(min_length=1)
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)


class SiteCredentialInput(StrictBaseModel):
    id: str | None = None
    name: str
    api_key: str = Field(min_length=1)
    enabled: bool = True


class SiteModel(StrictBaseModel):
    id: str
    credential_id: str
    credential_name: str = ""
    model_name: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)
    protocol: ProtocolKind | None = None


class SiteModelInput(StrictBaseModel):
    id: str | None = None
    credential_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    enabled: bool = True
    protocol: ProtocolKind


class SiteProtocolConfig(StrictBaseModel):
    id: str
    name: str = ""
    protocols: list[ProtocolKind] = Field(default_factory=list)
    enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: str = ""
    match_regex: str = ""
    base_url_id: str = Field(min_length=1)
    credential_id: str = ""
    auto_sync_enabled: bool = False
    models: list[SiteModel] = Field(default_factory=list)


class SiteProtocolConfigInput(StrictBaseModel):
    id: str | None = None
    name: str = ""
    protocols: list[ProtocolKind] = Field(default_factory=list)
    enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: str = ""
    match_regex: str = ""
    base_url_id: str = Field(min_length=1)
    credential_id: str = ""
    auto_sync_enabled: bool = False
    models: list[SiteModelInput] = Field(default_factory=list)

    @field_validator("match_regex")
    @classmethod
    def validate_match_regex(cls, pattern: str) -> str:
        return _validate_regex_pattern(pattern)


class SiteConfig(StrictBaseModel):
    id: str
    name: str
    base_urls: list[SiteBaseUrl] = Field(default_factory=list)
    credentials: list[SiteCredential] = Field(default_factory=list)
    protocols: list[SiteProtocolConfig] = Field(default_factory=list)


class SiteRuntimeSummary(StrictBaseModel):
    site_id: str
    site_name: str
    recent_request_count: int = 0
    latest_request_at: str | None = None
    latest_success: bool | None = None
    latest_status_code: int | None = None
    latest_error_message: str | None = None
    latest_channel_id: str | None = None
    latest_channel_name: str | None = None
    channel_summaries: list["SiteChannelRuntimeSummary"] = Field(default_factory=list)


class SiteChannelRuntimeSummary(StrictBaseModel):
    channel_id: str
    health_buckets: list["SiteChannelHealthBucket"] = Field(default_factory=list)


class SiteChannelHealthBucket(StrictBaseModel):
    started_at: str
    ended_at: str
    success_count: int = 0
    total_count: int = 0


class SiteCreate(StrictBaseModel):
    name: str
    base_urls: list[SiteBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    protocols: list[SiteProtocolConfigInput] = Field(default_factory=list)


class SiteUpdate(StrictBaseModel):
    name: str
    base_urls: list[SiteBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    protocols: list[SiteProtocolConfigInput] = Field(default_factory=list)


class SiteImportBaseUrlInput(StrictBaseModel):
    ref: str = ""
    url: HttpUrl
    name: str = ""
    enabled: bool = True

    _normalize_url = field_validator("url", mode="before")(normalize_base_url)


class SiteImportCredentialInput(StrictBaseModel):
    ref: str = ""
    name: str = ""
    api_key: str = Field(min_length=1)
    enabled: bool = True


class SiteImportModelInput(StrictBaseModel):
    model_name: str = Field(min_length=1)
    credential_ref: str = ""
    enabled: bool = True


class SiteImportProtocolInput(StrictBaseModel):
    protocol: ProtocolKind
    enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: str = ""
    match_regex: str = ""
    base_url_ref: str = ""
    credential_ref: str = ""
    models: list[SiteImportModelInput] = Field(default_factory=list)

    @field_validator("match_regex")
    @classmethod
    def validate_match_regex(cls, pattern: str) -> str:
        return _validate_regex_pattern(pattern)


class SiteImportItem(StrictBaseModel):
    name: str
    base_urls: list[SiteImportBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteImportCredentialInput] = Field(default_factory=list)
    protocols: list[SiteImportProtocolInput] = Field(default_factory=list)


class SiteBatchImportRequest(StrictBaseModel):
    sites: list[SiteImportItem] = Field(default_factory=list)


class SiteBatchImportSkipped(StrictBaseModel):
    index: int = Field(ge=0)
    name: str
    reason: str


class SiteBatchImportError(StrictBaseModel):
    index: int = Field(ge=0)
    field: str
    message: str


class SiteBatchImportResult(StrictBaseModel):
    committed: bool = False
    created_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    created: list[SiteConfig] = Field(default_factory=list)
    skipped: list[SiteBatchImportSkipped] = Field(default_factory=list)
    errors: list[SiteBatchImportError] = Field(default_factory=list)


class SiteModelFetchRequest(StrictBaseModel):
    base_url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    match_regex: str = ""
    credentials: list[SiteCredentialInput] = Field(
        default_factory=list, max_length=20
    )
    credential_ids: list[str] = Field(default_factory=list, max_length=20)

    _normalize_base_url = field_validator("base_url", mode="before")(normalize_base_url)

    @field_validator("match_regex")
    @classmethod
    def validate_match_regex(cls, pattern: str) -> str:
        return _validate_regex_pattern(pattern)


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
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: str = ""
    credential: SiteModelTestCredential
    model_name: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=2000)

    _normalize_base_url = field_validator("base_url", mode="before")(normalize_base_url)

    @field_validator("model_name", "prompt")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value cannot be empty")
        return normalized


class SiteModelTestResult(StrictBaseModel):
    success: bool
    status_code: int | None = None
    latency_ms: int = Field(default=0, ge=0)
    model_name: str
    credential_id: str
    output_text: str = ""
    error_message: str = ""
