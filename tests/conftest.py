from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_test_support import (
    assert_error,
    gateway_headers,
    json_response,
    openai_chat_channel_id,
    run_async,
    seed_request_log,
    valid_site_payload,
)
from lens_api.core.config import settings
from lens_api.core.db import Base
from lens_api.models import ProtocolKind

_INITIAL_SERVICE_STATE_CLOSED = False


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
    import lens_api.gateway.service.admin.backups as backups_mod
    import lens_api.gateway.service.admin.cronjobs as cronjobs_mod
    import lens_api.gateway.service.admin.gateway_api_keys as gateway_api_keys_mod
    import lens_api.gateway.service.admin.model_groups as model_groups_mod
    import lens_api.gateway.service.admin.model_prices as model_prices_mod
    import lens_api.gateway.service.admin.overview as overview_mod
    import lens_api.gateway.service.admin.request_logs as request_logs_mod
    import lens_api.gateway.service.admin.routing as routing_mod
    import lens_api.gateway.service.admin.settings as settings_mod
    import lens_api.gateway.service.admin.sites as sites_mod
    import lens_api.gateway.service.auth as auth_mod
    import lens_api.gateway.service.errors as errors_mod
    import lens_api.gateway.service.lifecycle as lifecycle_mod
    import lens_api.gateway.service.proxy_routes as proxy_routes_mod
    import lens_api.gateway.service.request_logger as request_logger_mod
    import lens_api.gateway.service.app_state as state_mod

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
        proxy_routes_mod,
        request_logger_mod,
        state_mod,
    ):
        monkeypatch.setattr(module, "app_state", state)


@pytest.fixture
def app_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[Any]:
    global _INITIAL_SERVICE_STATE_CLOSED

    db_path = tmp_path / "lens-test.db"
    monkeypatch.setattr(settings, "auth_secret_key", "test-secret")
    monkeypatch.setattr(
        settings, "database_url", f"sqlite+aiosqlite:///{db_path.as_posix()}"
    )
    import lens_api.gateway.service as service
    import lens_api.gateway.service.app_state as state_mod

    if not _INITIAL_SERVICE_STATE_CLOSED:
        run_async(_close_state(state_mod.app_state))
        _INITIAL_SERVICE_STATE_CLOSED = True

    state = state_mod.AppState()
    _patch_app_state(monkeypatch, state)
    monkeypatch.setattr(service, "lifespan", _noop_lifespan)

    run_async(_create_schema(state))
    run_async(state.cronjob_store.ensure_cronjobs(state_mod.CRONJOB_SPECS))
    run_async(state.admin_repo.ensure_default_admin("admin", "password"))

    try:
        yield state
    finally:
        run_async(_close_state(state))


@pytest.fixture
def client(app_state: Any) -> Iterator[TestClient]:
    import lens_api.gateway.service as service
    from lens_api.api.app import create_app

    with TestClient(create_app(service), raise_server_exceptions=False) as test_client:
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
        protocols: list[str] | None = None,
        items: list[dict[str, Any]] | None = None,
        route_group_id: str = "",
    ) -> dict[str, Any]:
        payload = {
            "name": name,
            "protocols": protocols or [ProtocolKind.OPENAI_CHAT.value],
            "strategy": "round_robin",
            "route_group_id": route_group_id,
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
