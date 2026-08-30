import json
import re
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .headers import validate_header_name, validate_header_value
from .validation import StrictBaseModel, _validate_regex_pattern


class HeaderRuleMatch(StrictBaseModel):
    path_regex: str | None = None
    model_regex: str | None = None
    protocol_regex: str | None = None

    @field_validator("path_regex", "model_regex", "protocol_regex")
    @classmethod
    def validate_regex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return _validate_regex_pattern(value, error_label="header rule regex")


class HeaderRule(StrictBaseModel):
    name: str
    action: Literal["remove", "override", "append"]
    value: str = ""
    match: HeaderRuleMatch | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_header_name(value)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        return validate_header_value(value)

    @model_validator(mode="after")
    def validate_action(self) -> "HeaderRule":
        if self.action in {"override", "append"} and not self.value:
            raise ValueError("Header override and append rules require value")
        return self


class ParamOverrideRule(StrictBaseModel):
    path: str = Field(min_length=1, max_length=200)
    action: Literal["set", "delete"]
    value: Any = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        value = value.strip()
        parts = value.split(".")
        if any(
            not part or not re.fullmatch(r"(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+)", part)
            for part in parts
        ):
            raise ValueError("Invalid parameter override path")
        if parts[0] == "model":
            raise ValueError("model cannot be overridden")
        if any(char in value for char in "\r\n\x00"):
            raise ValueError("Parameter override path must not contain CR, LF, or NUL")
        return value

    @model_validator(mode="after")
    def validate_action(self) -> "ParamOverrideRule":
        if self.action == "set" and self.value is None:
            raise ValueError("Parameter set rules require value")
        return self


class UpstreamHeadersConfig(StrictBaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    rules: list[HeaderRule] = Field(default_factory=list, max_length=100)


class CooldownDetectionRule(StrictBaseModel):
    """A validated body/status rule for upstream cooldown classification."""

    name: str = Field(min_length=1, max_length=100)
    status_code: int | None = Field(default=None, ge=100, le=599)
    body_regex: str | None = Field(default=None, max_length=1000)
    scope: Literal["key", "model", "channel"] = "model"
    category: Literal["auth", "not_found", "rate_limit", "server", "timeout", "network"]
    cooldown_seconds: int = Field(default=0, ge=0, le=604800)
    priority: int = Field(default=0, ge=-10000, le=10000)

    @field_validator("name", "body_regex")
    @classmethod
    def reject_control_characters(cls, value: str | None) -> str | None:
        if value is not None and any(ord(char) < 32 for char in value):
            raise ValueError("Rule values must not contain control characters")
        return value

    @field_validator("body_regex")
    @classmethod
    def validate_body_regex(cls, value: str | None) -> str | None:
        if value:
            _validate_regex_pattern(value, error_label="cooldown body regex")
        return value

    @model_validator(mode="after")
    def require_match_condition(self) -> "CooldownDetectionRule":
        if self.status_code is None and not self.body_regex:
            raise ValueError("Cooldown rule requires status_code or body_regex")
        return self


class CooldownDetectionRulesConfig(StrictBaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[CooldownDetectionRule] = Field(default_factory=list, max_length=100)


def serialize_upstream_headers_config_json(value: str) -> str:
    """Serialize upstream header rules into canonical JSON."""
    raw_value = value.strip()
    payload: Any = json.loads(raw_value) if raw_value else {}
    config = UpstreamHeadersConfig.model_validate(payload)
    return json.dumps(config.model_dump(mode="json"), ensure_ascii=True)


def serialize_upstream_param_override_config_json(value: str) -> str:
    """Serialize upstream parameter rules into canonical JSON."""
    raw_value = value.strip()
    payload: Any = json.loads(raw_value) if raw_value else {}
    config = UpstreamParamOverrideConfig.model_validate(payload)
    return json.dumps(config.model_dump(mode="json"), ensure_ascii=True)


def serialize_cooldown_detection_rules_json(value: str) -> str:
    """Serialize cooldown detection rules into canonical JSON."""
    raw_value = value.strip()
    payload: Any = json.loads(raw_value) if raw_value else {}
    config = CooldownDetectionRulesConfig.model_validate(payload)
    return json.dumps(config.model_dump(mode="json"), ensure_ascii=True)


class UpstreamParamOverrideConfig(StrictBaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[ParamOverrideRule] = Field(default_factory=list, max_length=100)
