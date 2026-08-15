import json
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, HttpUrl, field_validator

from .common import StrictBaseModel, _validate_regex_pattern, normalize_base_url
from .protocols import ChannelProxyMode, ModelSource, ProtocolKind


def _normalize_required_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Value cannot be empty")
    return normalized


def _normalize_required_text_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        item = _normalize_required_text(value)
        if item not in normalized:
            normalized.append(item)
    if not normalized:
        raise ValueError("At least one value is required")
    return normalized


def _normalize_site_tags(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        tag = value.strip()
        if not tag:
            raise ValueError("Site tags cannot be empty")
        if len(tag) > 80:
            raise ValueError("Site tags cannot exceed 80 characters")
        if tag not in normalized:
            normalized.append(tag)
    if len(normalized) > 20:
        raise ValueError("Sites cannot have more than 20 tags")
    return normalized


SiteTags = Annotated[list[str], AfterValidator(_normalize_site_tags)]


def _validate_param_override(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    try:
        override = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid param override JSON: {exc.msg} at line {exc.lineno} "
            f"column {exc.colno}"
        ) from exc
    if not isinstance(override, dict):
        raise ValueError("Param override must be a JSON object")
    if "model" in override:
        raise ValueError("Param override cannot override model")
    return normalized


_validate_match_regex = field_validator("match_regex")(_validate_regex_pattern)


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
    source: ModelSource = ModelSource.MANUAL


class SiteModelInput(StrictBaseModel):
    id: str | None = None
    credential_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    enabled: bool = True
    protocol: ProtocolKind
    source: ModelSource = ModelSource.MANUAL


class SiteSyncTarget(StrictBaseModel):
    credential_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
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
    base_url_id: str = Field(min_length=1)
    credential_ids: list[str] = Field(min_length=1)
    sync_targets: list[SiteSyncTarget] = Field(default_factory=list)
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
    base_url_id: str = Field(min_length=1)
    credential_ids: list[str] = Field(min_length=1)
    sync_targets: list[SiteSyncTarget] = Field(default_factory=list)
    models: list[SiteModelInput] = Field(default_factory=list)

    _normalize_credential_ids = field_validator("credential_ids")(
        _normalize_required_text_list
    )

    _normalize_param_override = field_validator("param_override")(
        _validate_param_override
    )


class SiteConfig(StrictBaseModel):
    id: str
    name: str
    enabled: bool
    tags: SiteTags
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
    tags: SiteTags = Field(default_factory=list)
    base_urls: list[SiteBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    protocols: list[SiteProtocolConfigInput] = Field(default_factory=list)


class SiteUpdate(StrictBaseModel):
    name: str
    tags: SiteTags = Field(default_factory=list)
    base_urls: list[SiteBaseUrlInput] = Field(default_factory=list)
    credentials: list[SiteCredentialInput] = Field(default_factory=list)
    protocols: list[SiteProtocolConfigInput] = Field(default_factory=list)


class SiteEnabledUpdate(StrictBaseModel):
    enabled: bool


class SiteImportBaseUrlInput(StrictBaseModel):
    ref: str
    url: HttpUrl
    name: str = ""
    enabled: bool = True

    _normalize_ref = field_validator("ref")(_normalize_required_text)
    _normalize_url = field_validator("url", mode="before")(normalize_base_url)


class SiteImportCredentialInput(StrictBaseModel):
    ref: str
    name: str = ""
    api_key: str = Field(min_length=1)
    enabled: bool = True

    _normalize_ref = field_validator("ref")(_normalize_required_text)


class SiteImportModelInput(StrictBaseModel):
    model_name: str = Field(min_length=1)
    credential_ref: str = Field(min_length=1)
    enabled: bool = True
    source: ModelSource = ModelSource.MANUAL


class SiteImportProtocolInput(StrictBaseModel):
    name: str
    protocol: ProtocolKind
    enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: str = ""
    base_url_ref: str
    credential_refs: list[str] = Field(min_length=1)
    models: list[SiteImportModelInput] = Field(default_factory=list)

    _normalize_identifiers = field_validator("name", "base_url_ref")(
        _normalize_required_text
    )
    _normalize_credential_refs = field_validator("credential_refs")(
        _normalize_required_text_list
    )

    _normalize_param_override = field_validator("param_override")(
        _validate_param_override
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


class SiteModelFetchRequest(StrictBaseModel):
    base_url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    match_regex: str = ""
    credentials: list[SiteCredentialInput] = Field(default_factory=list, max_length=20)
    credential_ids: list[str] = Field(default_factory=list, max_length=20)

    _normalize_base_url = field_validator("base_url", mode="before")(normalize_base_url)

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
    headers: dict[str, str] = Field(default_factory=dict)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: str = ""
    credential: SiteModelTestCredential
    model_name: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=2000)

    _normalize_base_url = field_validator("base_url", mode="before")(normalize_base_url)
    _normalize_non_empty_text = field_validator("model_name", "prompt")(
        _normalize_required_text
    )


class SiteModelTestResult(StrictBaseModel):
    success: bool
    status_code: int | None = None
    latency_ms: int = Field(default=0, ge=0)
    model_name: str
    credential_id: str
    output_text: str = ""
    error_message: str = ""
