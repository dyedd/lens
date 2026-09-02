import json
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .validation import StrictBaseModel, _validate_regex_pattern


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


def serialize_cooldown_detection_rules_json(value: str) -> str:
    """Serialize cooldown detection rules into canonical JSON."""
    raw_value = value.strip()
    payload: Any = json.loads(raw_value) if raw_value else {}
    config = CooldownDetectionRulesConfig.model_validate(payload)
    return json.dumps(config.model_dump(mode="json"), ensure_ascii=True)
