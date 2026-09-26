from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .protocols import ProtocolKind, RoutingStrategy
from .upstream_rules import HeaderRule, ParamOverrideRule
from .validation import StrictBaseModel, validate_regex_pattern


def _canonicalize_fallback_group_ids(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        group_id = item.strip()
        if not group_id:
            raise ValueError("Fallback model group ids must not be empty")
        if group_id in seen:
            raise ValueError(f"Duplicate fallback model group id: {group_id}")
        seen.add(group_id)
        result.append(group_id)
    return result


MAX_MATCH_MODELS = 200
MAX_MATCH_MODEL_NAME_LENGTH = 200


def canonicalize_match_models(value: list[str] | None) -> list[str] | None:
    """Trim, drop empty entries, and dedupe names case-insensitively in order."""
    if value is None:
        return None
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        name = item.strip()
        if not name or name.casefold() in seen:
            continue
        if len(name) > MAX_MATCH_MODEL_NAME_LENGTH:
            raise ValueError(
                f"Match model names must be at most {MAX_MATCH_MODEL_NAME_LENGTH} "
                "characters"
            )
        seen.add(name.casefold())
        result.append(name)
    if len(result) > MAX_MATCH_MODELS:
        raise ValueError(f"At most {MAX_MATCH_MODELS} match models are allowed")
    return result


def canonicalize_match_regex(value: str | None) -> str | None:
    """Trim the pattern; matching is always case-insensitive, so drop ``(?i)``."""
    if value is None:
        return None
    pattern = value.strip().removeprefix("(?i)").strip()
    return validate_regex_pattern(pattern, error_label="model group match regex")


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
    MODEL_UPSTREAM_MISSING = "model_upstream_missing"


class ModelGroup(StrictBaseModel):
    id: str
    name: str
    strategy: RoutingStrategy
    route_group_id: str = ""
    route_group_name: str = ""
    match_models: list[str] = Field(default_factory=list)
    match_regex: str = ""
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
    headers: list[HeaderRule] = Field(default_factory=list)
    fallback_group_ids: list[str] = Field(default_factory=list, max_length=20)
    input_price_per_million: float = 0.0
    image_input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    cache_read_price_per_million: float = 0.0
    cache_write_price_per_million: float = 0.0
    image_price_per_image: float = 0.0
    pricing_mode: Literal["free", "tokens", "non_tokens"] = "free"
    manual_override: bool = False
    items: list["ModelGroupItem"] = Field(default_factory=list)

    _validate_param_override = field_validator("param_override")(
        lambda value: [ParamOverrideRule.model_validate(item) for item in value]
    )
    _canonicalize_headers = field_validator("headers")(
        lambda value: [HeaderRule.model_validate(item) for item in value]
    )
    _validate_fallback_group_ids = field_validator("fallback_group_ids")(
        lambda value: _canonicalize_fallback_group_ids(value)
    )

    _canonicalize_match_models = field_validator("match_models")(
        canonicalize_match_models
    )
    _canonicalize_match_regex = field_validator("match_regex")(canonicalize_match_regex)

    @model_validator(mode="after")
    def clear_route_group_match_rules(self) -> "ModelGroup":
        if self.route_group_id.strip():
            self.match_models, self.match_regex = [], ""
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
    matched_by_rule: bool = False
    credential_mask: str = ""
    base_url: str = ""


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
    strategy: RoutingStrategy = RoutingStrategy.FAILOVER
    route_group_id: str = ""
    match_models: list[str] = Field(default_factory=list)
    match_regex: str = ""
    param_override: list[ParamOverrideRule] = Field(default_factory=list)
    headers: list[HeaderRule] = Field(default_factory=list)
    fallback_group_ids: list[str] = Field(default_factory=list, max_length=20)
    items: list[ModelGroupItemInput] = Field(default_factory=list)

    _validate_param_override = field_validator("param_override")(
        lambda value: [ParamOverrideRule.model_validate(item) for item in value]
    )
    _canonicalize_headers = field_validator("headers")(
        lambda value: [HeaderRule.model_validate(item) for item in value]
    )
    _validate_fallback_group_ids = field_validator("fallback_group_ids")(
        lambda value: _canonicalize_fallback_group_ids(value)
    )

    _canonicalize_match_models = field_validator("match_models")(
        canonicalize_match_models
    )
    _canonicalize_match_regex = field_validator("match_regex")(canonicalize_match_regex)

    @model_validator(mode="after")
    def clear_route_group_match_rules(self) -> "ModelGroupCreate":
        if self.route_group_id.strip():
            self.match_models, self.match_regex = [], ""
        return self


class ModelGroupUpdate(StrictBaseModel):
    name: str | None = None
    strategy: RoutingStrategy | None = None
    route_group_id: str | None = None
    match_models: list[str] | None = None
    match_regex: str | None = None
    param_override: list[ParamOverrideRule] | None = None
    headers: list[HeaderRule] | None = None
    fallback_group_ids: list[str] | None = Field(default=None, max_length=20)
    items: list[ModelGroupItemInput] | None = None

    _canonicalize_headers = field_validator("headers")(
        lambda value: (
            [HeaderRule.model_validate(item) for item in value]
            if value is not None
            else None
        )
    )

    _canonicalize_match_models = field_validator("match_models")(
        canonicalize_match_models
    )
    _canonicalize_match_regex = field_validator("match_regex")(canonicalize_match_regex)


class ModelGroupCandidateSubitem(ModelGroupItemInput):
    protocol_config_id: str
    protocol: ProtocolKind


class ModelGroupCandidateItem(StrictBaseModel):
    site_id: str
    channel_name: str
    credential_id: str = Field(min_length=1)
    credential_name: str = ""
    credential_number: int = Field(default=0, ge=0)
    credential_mask: str = ""
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
    protocol: ProtocolKind | None = None


class UnplacedModelProvider(StrictBaseModel):
    site_id: str
    channel_name: str
    credential_id: str
    credential_name: str = ""
    credential_number: int = Field(default=0, ge=0)
    credential_mask: str = ""
    base_url: str
    protocols: list[ProtocolKind] = Field(default_factory=list)


class UnplacedModelView(StrictBaseModel):
    model_name: str
    match_key: str
    similar_group_ids: list[str] = Field(default_factory=list)
    similar_group_names: list[str] = Field(default_factory=list)
    similar_model_names: list[str] = Field(default_factory=list)
    providers: list[UnplacedModelProvider] = Field(default_factory=list)


class UnplacedModelsResponse(StrictBaseModel):
    items: list[UnplacedModelView] = Field(default_factory=list)


class ModelGroupPlacementRequest(StrictBaseModel):
    model_names: list[str] | None = None


class ModelGroupPlacementResponse(StrictBaseModel):
    created: list[ModelGroupView] = Field(default_factory=list)
    unplaced: list[UnplacedModelView] = Field(default_factory=list)


class ModelGroupMergeRequest(StrictBaseModel):
    target_group_id: str = Field(min_length=1)
