from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.core.config import settings
from app.core.db import Base
from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.protocols import ProtocolKind, RequestLogLifecycleStatus

_INITIAL_SERVICE_STATE_CLOSED = False


def run_async(awaitable: Any) -> Any:
    """Run an awaitable to completion in a fresh event loop."""
    return asyncio.run(awaitable)


def valid_site_payload(
    *,
    name: str = "OpenAI Site",
    base_id: str = "base-1",
    credential_id: str = "cred-1",
    protocol_config_id: str = "pc-1",
    protocols: list[str] | None = None,
    model_name: str = "gpt-4o",
    credential_enabled: bool = True,
    base_url_enabled: bool = True,
    protocol_enabled: bool = True,
    model_enabled: bool = True,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Build a valid site API payload with optional field overrides."""
    protocol_values = protocols or [ProtocolKind.OPENAI_CHAT.value]
    return {
        "name": name,
        "tags": tags or [],
        "base_urls": [
            {
                "id": base_id,
                "url": "https://upstream.example/v1",
                "name": "primary",
                "enabled": base_url_enabled,
                "supported_protocols": protocol_values,
            }
        ],
        "credentials": [
            {
                "id": credential_id,
                "name": "primary-key",
                "api_key": "upstream-secret",
                "enabled": credential_enabled,
            }
        ],
        "protocols": [
            {
                "id": protocol_config_id,
                "name": "primary",
                "protocols": protocol_values,
                "enabled": protocol_enabled,
                "headers": [],
                "param_override": [],
                "base_url_id": base_id,
                "credential_ids": [credential_id],
                "models": [
                    {
                        "credential_id": credential_id,
                        "model_name": model_name,
                        "enabled": model_enabled,
                        "protocol": protocol,
                    }
                    for protocol in protocol_values
                ],
            }
        ],
    }


def gateway_headers(key: dict[str, Any]) -> dict[str, str]:
    """Build bearer authorization headers for a gateway API key."""
    return {"Authorization": f"Bearer {key['api_key']}"}


def openai_chat_channel_id(protocol_config_id: str = "pc-1") -> str:
    """Build the runtime OpenAI chat channel identifier used by tests."""
    return compose_runtime_channel_id(protocol_config_id, ProtocolKind.OPENAI_CHAT)


def seed_request_log(
    app_state: Any,
    *,
    protocol: str = ProtocolKind.OPENAI_CHAT.value,
    requested_group_name: str | None = "gpt-4o",
    resolved_group_name: str | None = "gpt-4o",
    channel_id: str | None = None,
    channel_name: str | None = "OpenAI Site",
    gateway_key_id: str | None = None,
    status_code: int | None = 200,
    success: bool = True,
    lifecycle_status: RequestLogLifecycleStatus | None = None,
    error_message: str | None = None,
    rate_multiplier: float | None = None,
    billing_mode: str = "tokens",
    billing_units: int = 0,
) -> Any:
    """Insert a representative request log through the current repository."""
    return run_async(
        app_state.request_log_store.create_request_log(
            protocol=protocol,
            user_agent="pytest",
            requested_group_name=requested_group_name,
            resolved_group_name=resolved_group_name,
            upstream_model_name=resolved_group_name,
            channel_id=channel_id or openai_chat_channel_id(),
            channel_name=channel_name,
            gateway_key_id=gateway_key_id,
            status_code=status_code,
            success=success,
            lifecycle_status=lifecycle_status
            or (
                RequestLogLifecycleStatus.SUCCEEDED
                if success
                else RequestLogLifecycleStatus.FAILED
            ),
            is_stream=False,
            first_token_latency_ms=12,
            latency_ms=34,
            input_tokens=10,
            cache_read_input_tokens=1,
            cache_write_input_tokens=2,
            output_tokens=20,
            total_tokens=30,
            input_cost_usd=0.01,
            output_cost_usd=0.02,
            total_cost_usd=0.03,
            rate_multiplier=rate_multiplier,
            billing_mode=billing_mode,
            billing_units=billing_units,
            request_content='{"model":"gpt-4o"}',
            response_content='{"ok":true}',
            attempts=[
                {
                    "channel_id": channel_id or openai_chat_channel_id(),
                    "channel_name": channel_name or "OpenAI Site",
                    "credential_id": "cred-1",
                    "credential_name": "primary-key",
                    "model_name": resolved_group_name,
                    "status_code": status_code,
                    "success": success,
                    "duration_ms": 34,
                    "error_message": error_message,
                }
            ],
            error_message=error_message,
        )
    )


def assert_error(response: Any, status_code: int, message: str | None = None) -> None:
    """Assert the standard API error response shape and optional message."""
    assert response.status_code == status_code, response.text
    payload = response.json()
    assert "error" in payload
    if message is not None:
        assert message in payload["error"]["message"]


def json_response(payload: dict[str, Any], status_code: int = 200) -> JSONResponse:
    """Create a JSON response for gateway test doubles."""
    return JSONResponse(payload, status_code=status_code)


@asynccontextmanager
async def _noop_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


async def _close_state(state: Any) -> None:
    await state.close_http_clients()
    await state.engine.dispose()


async def _create_schema(state: Any) -> None:
    async with state.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def _patch_app_state(monkeypatch: pytest.MonkeyPatch, state: Any) -> None:
    import app.gateway.service.admin.backups as backups_mod
    import app.gateway.service.admin.cronjobs as cronjobs_mod
    import app.gateway.service.admin.gateway_api_keys as gateway_api_keys_mod
    import app.gateway.service.admin.model_groups as model_groups_mod
    import app.gateway.service.admin.model_prices as model_prices_mod
    import app.gateway.service.admin.overview as overview_mod
    import app.gateway.service.admin.request_logs as request_logs_mod
    import app.gateway.service.admin.routing as routing_mod
    import app.gateway.service.admin.settings as settings_mod
    import app.gateway.service.admin.sites as sites_mod
    import app.gateway.service.app_state as state_mod
    import app.gateway.service.auth as auth_mod
    import app.gateway.service.errors as errors_mod
    import app.gateway.service.lifecycle as lifecycle_mod
    import app.gateway.service.proxy_attempt as proxy_attempt_mod
    import app.gateway.service.proxy_flow as proxy_flow_mod
    import app.gateway.service.proxy_routes as proxy_routes_mod
    import app.gateway.service.request_logger as request_logger_mod
    import app.gateway.service.routing_plan as routing_plan_mod

    for module in (
        backups_mod,
        cronjobs_mod,
        gateway_api_keys_mod,
        model_groups_mod,
        model_prices_mod,
        overview_mod,
        request_logs_mod,
        routing_mod,
        settings_mod,
        sites_mod,
        auth_mod,
        errors_mod,
        lifecycle_mod,
        proxy_attempt_mod,
        proxy_flow_mod,
        proxy_routes_mod,
        request_logger_mod,
        routing_plan_mod,
        state_mod,
    ):
        monkeypatch.setattr(module, "app_state", state)


@pytest.fixture
def app_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[Any]:
    global _INITIAL_SERVICE_STATE_CLOSED

    db_path = tmp_path / "lens-test.db"
    monkeypatch.setattr(settings, "auth_secret_key", "x" * 32)
    monkeypatch.setattr(
        settings, "database_url", f"sqlite+aiosqlite:///{db_path.as_posix()}"
    )
    import app.api.app as api_app
    import app.gateway.service.app_state as state_mod

    if not _INITIAL_SERVICE_STATE_CLOSED:
        run_async(_close_state(state_mod.app_state))
        _INITIAL_SERVICE_STATE_CLOSED = True

    state = state_mod.AppState()
    _patch_app_state(monkeypatch, state)
    monkeypatch.setattr(api_app, "lifespan", _noop_lifespan)

    run_async(_create_schema(state))
    run_async(state.cronjob_store.ensure_cronjobs(state_mod.CRONJOB_SPECS))
    run_async(state.admin_repo.ensure_default_admin("admin", "password"))

    try:
        yield state
    finally:
        run_async(_close_state(state))


@pytest.fixture
def client(app_state: Any) -> Iterator[TestClient]:
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/admin/session",
        json={"username": "admin", "password": "password"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def create_site(client: TestClient, admin_headers: dict[str, str]) -> Any:
    def _create_site(payload: dict[str, Any] | None = None) -> dict[str, Any]:
        response = client.post(
            "/api/admin/sites",
            headers=admin_headers,
            json=payload or valid_site_payload(),
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create_site


@pytest.fixture
def create_model_group(
    client: TestClient,
    admin_headers: dict[str, str],
) -> Any:
    def _create_model_group(
        *,
        name: str = "gpt-4o",
        items: list[dict[str, Any]] | None = None,
        route_group_id: str = "",
    ) -> dict[str, Any]:
        payload = {
            "name": name,
            "strategy": "round_robin",
            "route_group_id": route_group_id,
            "headers": [],
            "param_override": [],
            "items": items or [],
        }
        response = client.post(
            "/api/admin/model-groups", headers=admin_headers, json=payload
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create_model_group


@pytest.fixture
def create_gateway_key(
    client: TestClient,
    admin_headers: dict[str, str],
) -> Any:
    def _create_gateway_key(**overrides: Any) -> dict[str, Any]:
        payload = {
            "remark": "test key",
            "enabled": True,
            "allowed_models": [],
            "max_cost_usd": 0,
            "expires_at": None,
            **overrides,
        }
        response = client.post(
            "/api/admin/gateway-api-keys", headers=admin_headers, json=payload
        )
        assert response.status_code == 200, response.text
        return response.json()

    return _create_gateway_key


@pytest.fixture
def create_site_group_and_key(
    create_site: Any,
    create_model_group: Any,
    create_gateway_key: Any,
) -> Any:
    def _create_site_group_and_key(
        *,
        model_name: str = "gpt-4o",
        gateway_overrides: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        site = create_site(valid_site_payload(model_name=model_name))
        group = create_model_group(
            name=model_name,
            items=[
                {
                    "channel_id": openai_chat_channel_id(),
                    "credential_id": "cred-1",
                    "model_name": model_name,
                    "enabled": True,
                }
            ],
        )
        key = create_gateway_key(**(gateway_overrides or {}))
        return site, group, key

    return _create_site_group_and_key
