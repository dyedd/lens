import json
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from .common import StrictBaseModel, _validate_regex_pattern
from .protocols import (
    UpstreamHeaderRuleMatchType,
    UpstreamParamOverrideRuleMatchType,
)

def _normalize_header_map(headers: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    lower_to_key: dict[str, str] = {}
    for raw_key, raw_value in headers.items():
        key = str(raw_key).strip()
        if not key:
            continue
        lower_key = key.lower()
        existing_key = lower_to_key.get(lower_key)
        if existing_key is not None:
            normalized.pop(existing_key, None)
        value = str(raw_value).strip()
        lower_to_key[lower_key] = key
        normalized[key] = value
    return normalized


class UpstreamHeaderRule(StrictBaseModel):
    enabled: bool = True
    name: str = ""
    match_type: UpstreamHeaderRuleMatchType = UpstreamHeaderRuleMatchType.EXACT
    models: list[str] = Field(default_factory=list)
    pattern: str = ""
    headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("name", "pattern")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("models")
    @classmethod
    def normalize_models(cls, models: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in models:
            model = str(item).strip()
            if not model or model in seen:
                continue
            seen.add(model)
            normalized.append(model)
        return normalized

    @field_validator("headers")
    @classmethod
    def normalize_headers(cls, headers: dict[str, str]) -> dict[str, str]:
        return _normalize_header_map(headers)

    @model_validator(mode="after")
    def validate_matcher(self) -> "UpstreamHeaderRule":
        if self.match_type == UpstreamHeaderRuleMatchType.REGEX:
            if not self.pattern:
                raise ValueError("Regex upstream header rule requires pattern")
            _validate_regex_pattern(
                self.pattern, error_label="upstream header rule regex"
            )
        return self


class UpstreamHeadersConfig(StrictBaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    global_headers: dict[str, str] = Field(default_factory=dict, alias="global")
    rules: list[UpstreamHeaderRule] = Field(default_factory=list)

    @field_validator("global_headers")
    @classmethod
    def normalize_global_headers(cls, headers: dict[str, str]) -> dict[str, str]:
        return _normalize_header_map(headers)


def normalize_upstream_headers_config_json(value: str) -> str:
    """Normalize upstream header configuration into canonical JSON."""
    raw_value = value.strip()
    if raw_value:
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            payload = {}
        config = UpstreamHeadersConfig.model_validate(payload)
    else:
        config = UpstreamHeadersConfig()
    return json.dumps(config.model_dump(mode="json", by_alias=True), ensure_ascii=True)


class UpstreamParamOverrideRule(StrictBaseModel):
    enabled: bool = True
    name: str = ""
    match_type: UpstreamParamOverrideRuleMatchType = (
        UpstreamParamOverrideRuleMatchType.EXACT
    )
    models: list[str] = Field(default_factory=list)
    pattern: str = ""
    override: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "pattern")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("models")
    @classmethod
    def normalize_models(cls, models: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in models:
            model = str(item).strip()
            if not model or model in seen:
                continue
            seen.add(model)
            normalized.append(model)
        return normalized

    @model_validator(mode="after")
    def validate_matcher(self) -> "UpstreamParamOverrideRule":
        if "model" in self.override:
            raise ValueError("model cannot be overridden")
        if self.match_type == UpstreamParamOverrideRuleMatchType.REGEX:
            if not self.pattern:
                raise ValueError("Regex upstream param override rule requires pattern")
            _validate_regex_pattern(
                self.pattern, error_label="upstream param override rule regex"
            )
        return self


class UpstreamParamOverrideConfig(StrictBaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    global_override: dict[str, Any] = Field(default_factory=dict, alias="global")
    rules: list[UpstreamParamOverrideRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_global_override(self) -> "UpstreamParamOverrideConfig":
        if "model" in self.global_override:
            raise ValueError("model cannot be overridden")
        return self


def normalize_upstream_param_override_config_json(value: str) -> str:
    """Normalize upstream parameter overrides into canonical JSON."""
    raw_value = value.strip()
    if raw_value:
        payload = json.loads(raw_value)
        config = UpstreamParamOverrideConfig.model_validate(payload)
    else:
        config = UpstreamParamOverrideConfig()
    return json.dumps(config.model_dump(mode="json", by_alias=True), ensure_ascii=True)



