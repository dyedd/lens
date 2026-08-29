from typing import Annotated, Literal

from pydantic import AfterValidator, Field, HttpUrl, field_validator, model_validator

from ..core.urls import canonicalize_base_url
from .model_groups import ModelGroupEnsureFromSiteResponse, ModelGroupEnsureModelInput
from .protocols import ChannelProxyMode, ModelSource, ProtocolKind
from .upstream_rules import HeaderRule, ParamOverrideRule
from .validation import StrictBaseModel, _validate_regex_pattern


def _require_non_empty_text(value: str) -> str:
    trimmed_text = value.strip()
    if not trimmed_text:
        raise ValueError("Value cannot be empty")
    return trimmed_text


def _canonicalize_text_list(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    for value in values:
        item = _require_non_empty_text(value)
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


_validate_match_regex = field_validator("match_regex")(_validate_regex_pattern)


class SiteBaseUrl(StrictBaseModel):
    id: str
    url: HttpUrl
    name: str = ""
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)
    supported_protocols: list[ProtocolKind] = Field(default_factory=list)

    _canonicalize_url = field_validator("url", mode="before")(canonicalize_base_url)


class SiteBaseUrlInput(StrictBaseModel):
    id: str | None = None
    url: HttpUrl
    name: str = ""
    enabled: bool = True
    supported_protocols: list[ProtocolKind] = Field(default_factory=list)

    _canonicalize_url = field_validator("url", mode="before")(canonicalize_base_url)


class SiteCredential(StrictBaseModel):
    id: str
    name: str
    api_key: str = Field(min_length=1)
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)
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
    enabled: bool = True
    rate_source: SiteCredentialRateSource = "none"
    rate_protocol_config_id: str = ""
    rate_group: str = ""

    @model_validator(mode="after")
    def validate_rate_config(self) -> "SiteCredentialInput":
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
    headers: list[HeaderRule] = Field(default_factory=list)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
    base_url_id: str = Field(min_length=1)
    credential_ids: list[str] = Field(min_length=1)
    sync_targets: list[SiteSyncTarget] = Field(default_factory=list)
    models: list[SiteModel] = Field(default_factory=list)


class SiteProtocolConfigInput(StrictBaseModel):
    id: str | None = None
    name: str = ""
    protocols: list[ProtocolKind] = Field(default_factory=list)
    enabled: bool = True
    headers: list[HeaderRule] = Field(default_factory=list)
    proxy_mode: ChannelProxyMode = ChannelProxyMode.INHERIT
    channel_proxy: str = ""
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
    base_url_id: str = Field(min_length=1)
    credential_ids: list[str] = Field(min_length=1)
    sync_targets: list[SiteSyncTarget] = Field(default_factory=list)
    models: list[SiteModelInput] = Field(default_factory=list)

    _canonicalize_credential_ids = field_validator("credential_ids")(
        _canonicalize_text_list
    )


class SiteConfig(StrictBaseModel):
    id: str
    name: str
    enabled: bool
    tags: SiteTags
    base_urls: list[SiteBaseUrl] = Field(default_factory=list)
    credentials: list[SiteCredential] = Field(default_factory=list)
    protocols: list[SiteProtocolConfig] = Field(default_factory=list)


class HealthBucket(StrictBaseModel):
    started_at: str
    ended_at: str
    success_count: int = 0
    total_count: int = 0


class HealthItem(StrictBaseModel):
    name: str
    success_count: int = 0
    total_count: int = 0
    buckets: list[HealthBucket] = Field(default_factory=list)


class HealthSummary(StrictBaseModel):
    started_at: str
    ended_at: str
    items: list[HealthItem] = Field(default_factory=list)
    next_offset: int | None = None


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
