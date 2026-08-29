from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .headers import canonicalize_header_map
from .param_override import validate_param_override
from .protocols import (
    ModelGroupSyncFilterMode,
    ProtocolKind,
    RoutingStrategy,
)
from .validation import StrictBaseModel, _validate_regex_pattern


class ModelGroupItemState(str, Enum):
    READY = "ready"
    DISABLED = "disabled"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


class ModelGroupItemReason(str, Enum):
    MANUAL_DISABLED = "manual_disabled"
    CHANNEL_NOT_FOUND = "channel_not_found"
    CHANNEL_DISABLED = "channel_disabled"
    CREDENTIAL_NOT_FOUND = "credential_not_found"
    CREDENTIAL_DISABLED = "credential_disabled"
    MODEL_NOT_FOUND = "model_not_found"
    MODEL_DISABLED = "model_disabled"


class ModelGroup(StrictBaseModel):
    id: str
    name: str
    strategy: RoutingStrategy
    route_group_id: str = ""
    route_group_name: str = ""
    sync_filter_mode: ModelGroupSyncFilterMode = ModelGroupSyncFilterMode.NONE
    sync_filter_query: str = ""
    param_override: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    cache_read_price_per_million: float = 0.0
    cache_write_price_per_million: float = 0.0
    image_price_per_image: float = 0.0
    pricing_mode: Literal["tokens", "non_tokens"] = "tokens"
    items: list["ModelGroupItem"] = Field(default_factory=list)

    _validate_param_override = field_validator("param_override")(
        validate_param_override
    )
    _canonicalize_headers = field_validator("headers")(canonicalize_header_map)

    @model_validator(mode="after")
    def validate_sync_filter(self) -> "ModelGroup":
        self.sync_filter_mode, self.sync_filter_query = (
            canonicalize_model_group_sync_filter(
                self.sync_filter_mode,
                self.sync_filter_query,
                route_group_id=self.route_group_id,
            )
        )
        return self


class ModelGroupItem(StrictBaseModel):
    channel_id: str
    channel_name: str = ""
    protocol: ProtocolKind | None = None
    credential_id: str = Field(min_length=1)
    credential_name: str = ""
    credential_number: int = Field(default=0, ge=0)
    model_name: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)


class ModelGroupItemView(ModelGroupItem):
    protocol_config_id: str
    site_id: str | None
    rate_source: Literal["none", "sub2api", "newapi"] = "none"
    rate_multiplier: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    state: ModelGroupItemState
    reasons: list[ModelGroupItemReason] = Field(default_factory=list)


class ModelGroupView(ModelGroup):
    client_protocols: list[ProtocolKind] = Field(default_factory=list)
    items: list[ModelGroupItemView] = Field(default_factory=list)


class ModelGroupItemInput(StrictBaseModel):
    channel_id: str = Field(min_length=1)
    credential_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    enabled: bool = True


class ModelGroupCreate(StrictBaseModel):
    name: str
    strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN
    route_group_id: str = ""
    sync_filter_mode: ModelGroupSyncFilterMode = ModelGroupSyncFilterMode.NONE
    sync_filter_query: str = ""
    param_override: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    items: list[ModelGroupItemInput] = Field(default_factory=list)

    _validate_param_override = field_validator("param_override")(
        validate_param_override
    )
    _canonicalize_headers = field_validator("headers")(canonicalize_header_map)

    @model_validator(mode="after")
    def validate_sync_filter(self) -> "ModelGroupCreate":
        self.sync_filter_mode, self.sync_filter_query = (
            canonicalize_model_group_sync_filter(
                self.sync_filter_mode,
                self.sync_filter_query,
                route_group_id=self.route_group_id,
            )
        )
        return self


class ModelGroupUpdate(StrictBaseModel):
    name: str | None = None
    strategy: RoutingStrategy | None = None
    route_group_id: str | None = None
    sync_filter_mode: ModelGroupSyncFilterMode | None = None
    sync_filter_query: str | None = None
    param_override: str | None = None
    headers: dict[str, str] | None = None
    items: list[ModelGroupItemInput] | None = None

    @field_validator("param_override")
    @classmethod
    def validate_param_override(cls, value: str | None) -> str | None:
        return validate_param_override(value) if value is not None else None

    @field_validator("headers")
    @classmethod
    def canonicalize_headers(
        cls, value: dict[str, str] | None
    ) -> dict[str, str] | None:
        return canonicalize_header_map(value) if value is not None else None

    @model_validator(mode="after")
    def validate_sync_filter(self) -> "ModelGroupUpdate":
        if self.sync_filter_mode is None and self.sync_filter_query is None:
            return self
        mode = (
            self.sync_filter_mode
            if self.sync_filter_mode is not None
            else ModelGroupSyncFilterMode.NONE
        )
        query = self.sync_filter_query if self.sync_filter_query is not None else ""
        self.sync_filter_mode, self.sync_filter_query = (
            canonicalize_model_group_sync_filter(
                mode,
                query,
                route_group_id=self.route_group_id or "",
            )
        )
        return self


def canonicalize_model_group_sync_filter(
    mode: ModelGroupSyncFilterMode,
    query: str,
    *,
    route_group_id: str = "",
) -> tuple[ModelGroupSyncFilterMode, str]:
    """Canonicalize model group sync filtering for persisted configuration."""
    trimmed_query = query.strip()
    if route_group_id.strip() or not trimmed_query:
        return ModelGroupSyncFilterMode.NONE, ""
    if mode == ModelGroupSyncFilterMode.NONE:
        return ModelGroupSyncFilterMode.NONE, ""
    if mode == ModelGroupSyncFilterMode.REGEX:
        _validate_regex_pattern(trimmed_query, error_label="model group sync regex")
    return mode, trimmed_query


class ModelGroupCandidateSubitem(ModelGroupItemInput):
    protocol_config_id: str
    protocol: ProtocolKind


class ModelGroupCandidateItem(StrictBaseModel):
    site_id: str
    channel_name: str
    credential_id: str = Field(min_length=1)
    credential_name: str = ""
    credential_number: int = Field(default=0, ge=0)
    rate_source: Literal["none", "sub2api", "newapi"] = "none"
    rate_multiplier: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    base_url: str
    model_name: str
    protocol_config_id: str
    protocols: list[ProtocolKind] = Field(default_factory=list)
    items: list[ModelGroupCandidateSubitem] = Field(default_factory=list)


class ModelGroupCandidatesRequest(StrictBaseModel):
    items: list[ModelGroupItemInput] = Field(default_factory=list)


class ModelGroupCandidatesResponse(StrictBaseModel):
    candidates: list[ModelGroupCandidateItem] = Field(default_factory=list)
    evaluated_items: list[ModelGroupItemView] = Field(default_factory=list)


class ModelGroupModelTestRequest(StrictBaseModel):
    channel_id: str = Field(min_length=1)
    credential_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=2000)


class ModelGroupEnsureModelInput(StrictBaseModel):
    protocol_config_id: str = Field(min_length=1)
    credential_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    group_name: str = ""
    protocols: list[ProtocolKind] = Field(min_length=1)


class ModelGroupEnsureFromSiteRequest(StrictBaseModel):
    site_id: str = Field(min_length=1)
    dry_run: bool = True
    models: list[ModelGroupEnsureModelInput] = Field(default_factory=list)


class ModelGroupEnsureResultItem(StrictBaseModel):
    group_id: str = ""
    group_name: str
    protocol_config_id: str
    credential_id: str
    model_name: str
    protocols: list[ProtocolKind] = Field(default_factory=list)
    status: Literal["create", "update", "unchanged", "skipped"]
    added_count: int = Field(default=0, ge=0)
    existing_count: int = Field(default=0, ge=0)
    skipped_reason: str = ""


class ModelGroupEnsureFromSiteResponse(StrictBaseModel):
    dry_run: bool
    created_count: int = Field(default=0, ge=0)
    updated_count: int = Field(default=0, ge=0)
    unchanged_count: int = Field(default=0, ge=0)
    skipped_count: int = Field(default=0, ge=0)
    items: list[ModelGroupEnsureResultItem] = Field(default_factory=list)
