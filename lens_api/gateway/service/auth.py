from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from packaging import version
from starlette.concurrency import run_in_threadpool

from ...core.auth import create_access_token, decode_access_token
from ...core.config import settings
from ...core.protocol_reachability import build_protocol_conversion_matrix
from ...models import (
    AdminLoginRequest,
    AdminPasswordChangeRequest,
    AdminProfile,
    AdminProfileUpdateRequest,
    AdminProfileUpdateResponse,
    AppInfo,
    AuthTokenResponse,
    GatewayApiKey,
    PublicBranding,
    VersionCheckResult,
)
from ...persistence.entities import AdminUserEntity
from ...persistence.shared import (
    SETTING_LATEST_VERSION,
    SETTING_LATEST_VERSION_URL,
    SETTING_VERSION_CHECK_AT,
)
from .app_state import _read_system_version, app_state, logger
from .lifecycle import auth_scheme


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> AdminUserEntity:
    """Authenticate and return the active administrative user."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    payload = await run_in_threadpool(
        decode_access_token, credentials.credentials, settings.auth_secret_key
    )
    username = payload.get("sub")

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    admin = await app_state.admin_repo.find_by_username(username)
    if admin is None or admin.is_active != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found"
        )

    return admin


async def get_current_gateway_key(request: Request) -> GatewayApiKey:
    """Authenticate and return the gateway API key for a request."""
    authorization = request.headers.get("authorization", "")
    x_api_key = request.headers.get("x-api-key", "")
    x_goog_api_key = request.headers.get("x-goog-api-key", "")

    secret = ""
    if authorization.lower().startswith("bearer "):
        secret = authorization[7:].strip()
    elif x_api_key:
        secret = x_api_key.strip()
    elif x_goog_api_key:
        secret = x_goog_api_key.strip()

    if not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing gateway API key"
        )

    gateway_key = await app_state.gateway_api_key_repo.find_gateway_api_key_by_secret(
        secret
    )

    if gateway_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid gateway API key"
        )

    if not gateway_key.enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gateway API key is disabled",
        )

    if _is_gateway_key_expired(gateway_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gateway API key has expired",
        )

    if (
        gateway_key.max_cost_usd > 0
        and gateway_key.spent_cost_usd >= gateway_key.max_cost_usd
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gateway API key has reached the max balance",
        )

    return gateway_key


def _is_gateway_key_expired(gateway_key: GatewayApiKey) -> bool:
    if not gateway_key.expires_at:
        return False
    try:
        expires_at = datetime.fromisoformat(
            gateway_key.expires_at.replace("Z", "+00:00")
        )
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)


def _gateway_key_allows_model(
    gateway_key: GatewayApiKey, model_name: str | None
) -> bool:
    if not gateway_key.allowed_models:
        return True
    if not model_name:
        return True
    normalized_allowed = {
        item.strip().lower() for item in gateway_key.allowed_models if item.strip()
    }
    return model_name.strip().lower() in normalized_allowed


def _has_version_update(latest_version: str, current_version: str) -> bool:
    if not latest_version:
        return False
    try:
        return version.parse(latest_version) > version.parse(current_version)
    except version.InvalidVersion:
        logger.warning(
            "Invalid version string when comparing %r vs %r",
            latest_version,
            current_version,
        )
        return False


async def get_public_branding() -> PublicBranding:
    """Return public site branding settings."""
    branding = await app_state.settings_repo.get_branding_settings()
    return PublicBranding(
        site_name=branding["site_name"], logo_url=branding["site_logo_url"]
    )


async def get_app_info(_: Any = Depends(get_current_admin)) -> AppInfo:
    """Return administrative application metadata and capabilities."""
    runtime = await app_state.settings_repo.get_runtime_settings()
    return AppInfo(
        system_version=_read_system_version(),
        site_name=str(runtime["site_name"]),
        logo_url=str(runtime["site_logo_url"]),
        time_zone=str(runtime["time_zone"]),
        protocol_conversions=build_protocol_conversion_matrix(),
    )


async def check_version(_: Any = Depends(get_current_admin)) -> VersionCheckResult:
    """Return the latest stored application update status."""
    current_version = _read_system_version()

    settings = await app_state.settings_repo.list_settings()
    settings_dict = {setting.key: setting.value for setting in settings}

    latest_version = settings_dict.get(SETTING_LATEST_VERSION, "")
    latest_url = settings_dict.get(SETTING_LATEST_VERSION_URL, "")
    checked_at = settings_dict.get(SETTING_VERSION_CHECK_AT, "")

    has_update = _has_version_update(latest_version, current_version)

    return VersionCheckResult(
        current_version=current_version,
        latest_version=latest_version if has_update else "",
        release_url=latest_url if has_update else "",
        has_update=has_update,
        checked_at=checked_at,
    )


async def login(payload: AdminLoginRequest) -> AuthTokenResponse:
    """Authenticate an administrator and issue an access token."""
    user = await app_state.admin_repo.authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token, expires_in = await _create_admin_access_token(user.username)
    return AuthTokenResponse(access_token=access_token, expires_in=expires_in)


async def get_current_admin_profile(
    admin: AdminUserEntity = Depends(get_current_admin),
) -> AdminProfile:
    """Return the authenticated administrator profile."""
    return AdminProfile(id=admin.id, username=admin.username)


async def update_profile(
    payload: AdminProfileUpdateRequest,
    admin: AdminUserEntity = Depends(get_current_admin),
) -> AdminProfileUpdateResponse:
    """Update the administrator profile and issue a replacement token."""
    normalized_username = payload.username.strip()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="Username is required")

    updated_admin = await app_state.admin_repo.update_profile(
        admin.username,
        normalized_username,
        payload.current_password,
        payload.new_password,
    )

    access_token, expires_in = await _create_admin_access_token(updated_admin.username)
    return AdminProfileUpdateResponse(
        access_token=access_token,
        expires_in=expires_in,
        profile=AdminProfile(id=updated_admin.id, username=updated_admin.username),
    )


async def change_password(
    payload: AdminPasswordChangeRequest,
    admin: AdminUserEntity = Depends(get_current_admin),
) -> Response:
    """Change the authenticated administrator password."""
    await app_state.admin_repo.update_password(
        admin.username, payload.current_password, payload.new_password
    )
    return Response(status_code=204)


async def _create_admin_access_token(username: str) -> tuple[str, int]:
    runtime = await app_state.settings_repo.get_runtime_settings()
    return await run_in_threadpool(
        create_access_token,
        username,
        settings.auth_secret_key,
        int(runtime["auth_access_token_minutes"]),
    )
