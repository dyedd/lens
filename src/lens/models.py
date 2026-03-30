from __future__ import annotations

from enum import Enum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class ProtocolKind(str, Enum):
    OPENAI_CHAT = "openai_chat"
    OPENAI_RESPONSES = "openai_responses"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class ProviderStatus(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    protocol: ProtocolKind
    base_url: HttpUrl
    api_key: str = Field(min_length=1)
    model_name: str | None = None
    status: ProviderStatus = ProviderStatus.ENABLED
    weight: int = Field(default=1, ge=1)
    priority: int = Field(default=100, ge=1)
    headers: dict[str, str] = Field(default_factory=dict)
    model_patterns: list[str] = Field(default_factory=list)


class ProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    protocol: ProtocolKind
    base_url: HttpUrl
    api_key: str = Field(min_length=1)
    model_name: str | None = None
    status: ProviderStatus = ProviderStatus.ENABLED
    weight: int = Field(default=1, ge=1)
    priority: int = Field(default=100, ge=1)
    headers: dict[str, str] = Field(default_factory=dict)
    model_patterns: list[str] = Field(default_factory=list)

    @field_validator("model_patterns")
    @classmethod
    def validate_model_patterns(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"Invalid regex pattern: {pattern}. {exc}") from exc
        return patterns


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    base_url: HttpUrl | None = None
    api_key: str | None = Field(default=None, min_length=1)
    model_name: str | None = None
    status: ProviderStatus | None = None
    weight: int | None = Field(default=None, ge=1)
    priority: int | None = Field(default=None, ge=1)
    headers: dict[str, str] | None = None
    model_patterns: list[str] | None = None

    @field_validator("model_patterns")
    @classmethod
    def validate_model_patterns(cls, patterns: list[str] | None) -> list[str] | None:
        if patterns is None:
            return None
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"Invalid regex pattern: {pattern}. {exc}") from exc
        return patterns


class ProviderHealth(BaseModel):
    provider_id: str
    consecutive_failures: int = 0
    last_error: str | None = None


class RouteState(BaseModel):
    protocol: ProtocolKind
    next_index: int = 0
    provider_ids: list[str] = Field(default_factory=list)
    requested_model: str | None = None


class RoutePreview(BaseModel):
    protocol: ProtocolKind
    requested_model: str | None = None
    matched_provider_ids: list[str] = Field(default_factory=list)


class RoutePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: ProtocolKind
    model: str | None = None


class RouterSnapshot(BaseModel):
    routes: list[RouteState]
    health: list[ProviderHealth]


class ErrorResponse(BaseModel):
    error: dict[str, Any]


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminProfile(BaseModel):
    id: int
    username: str
