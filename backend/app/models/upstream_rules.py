import json
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from .headers import canonicalize_header_map
from .validation import StrictBaseModel


class UpstreamHeadersConfig(StrictBaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    global_headers: dict[str, str] = Field(default_factory=dict, alias="global")

    @field_validator("global_headers")
    @classmethod
    def canonicalize_global_headers(cls, headers: dict[str, str]) -> dict[str, str]:
        return canonicalize_header_map(headers)


def serialize_upstream_headers_config_json(value: str) -> str:
    """Serialize upstream header configuration into canonical JSON."""
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


class UpstreamParamOverrideConfig(StrictBaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    global_override: dict[str, Any] = Field(default_factory=dict, alias="global")

    @model_validator(mode="after")
    def validate_global_override(self) -> "UpstreamParamOverrideConfig":
        if "model" in self.global_override:
            raise ValueError("model cannot be overridden")
        return self


def serialize_upstream_param_override_config_json(value: str) -> str:
    """Serialize upstream parameter overrides into canonical JSON."""
    raw_value = value.strip()
    if raw_value:
        payload = json.loads(raw_value)
        config = UpstreamParamOverrideConfig.model_validate(payload)
    else:
        config = UpstreamParamOverrideConfig()
    return json.dumps(config.model_dump(mode="json", by_alias=True), ensure_ascii=True)
