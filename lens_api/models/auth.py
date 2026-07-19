from typing import Any

from pydantic import Field, field_validator

from ..core.auth import validate_admin_password
from .common import StrictBaseModel


class ErrorResponse(StrictBaseModel):
    error: dict[str, Any]


class AdminLoginRequest(StrictBaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthTokenResponse(StrictBaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminProfile(StrictBaseModel):
    id: int
    username: str


class AdminPasswordChangeRequest(StrictBaseModel):
    current_password: str = Field(min_length=1)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_admin_password(value)


class AdminProfileUpdateRequest(StrictBaseModel):
    username: str = Field(min_length=1)
    current_password: str = ""
    new_password: str = ""

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_admin_password(value) if value else value


class AdminProfileUpdateResponse(StrictBaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    profile: AdminProfile


class PublicBranding(StrictBaseModel):
    site_name: str
    logo_url: str = ""


class AppInfo(StrictBaseModel):
    system_version: str
    site_name: str
    logo_url: str = ""
    time_zone: str
    protocol_conversions: dict[str, list[str]] = Field(default_factory=dict)


class VersionCheckResult(StrictBaseModel):
    current_version: str
    latest_version: str
    release_url: str
    has_update: bool
    checked_at: str
