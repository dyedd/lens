from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from conftest import (
    assert_error,
    openai_chat_channel_id,
    run_async,
    seed_request_log,
)
from lens_api.models import (
    ChannelModelSyncResponse,
    ProtocolKind,
    SiteModelTestRequest,
    SiteModelTestResult,
)
from lens_api.persistence.shared import (
    SETTING_FIRST_TOKEN_TIMEOUT_SECONDS,
    SettingItem,
)


def _model_test_payload(protocol: ProtocolKind) -> dict[str, Any]:
    return {
        "protocol": protocol.value,
        "base_url": "https://upstream.example/v1",
        "credential": {
            "id": "cred-a",
            "name": "primary",
            "api_key": "upstream-secret",
        },
        "model_name": "test-model",
        "prompt": "ping",
    }


def test_site_runtime_summaries_include_recent_request_log(
    client,
    admin_headers,
    app_state,
    create_site,
) -> None:
    site = create_site()
    seed_request_log(app_state, channel_id=openai_chat_channel_id())

    response = client.get("/api/admin/sites/runtime", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["site_id"] == site["id"]
    assert payload[0]["recent_request_count"] == 1
    assert payload[0]["latest_success"] is True
    assert payload[0]["channel_summaries"][0]["channel_id"] == openai_chat_channel_id()


def test_fetch_site_models_uses_selected_credentials(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    async def fake_fetch(channel: Any) -> list[str]:
        assert channel.keys[0].id == "cred-a"
        return ["gpt-4o", "gpt-4o-mini"]

    import lens_api.gateway.service.admin.sites as sites

    monkeypatch.setattr(sites, "_fetch_upstream_models", fake_fetch)

    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example/v1",
            "credentials": [
                {
                    "id": "cred-a",
                    "name": "primary",
                    "api_key": "upstream-secret",
                    "enabled": True,
                }
            ],
            "credential_ids": ["cred-a"],
        },
    )

    assert response.status_code == 200
    assert [item["model_name"] for item in response.json()] == [
        "gpt-4o",
        "gpt-4o-mini",
    ]


def test_fetch_site_models_reports_missing_credentials(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={"base_url": "https://upstream.example/v1", "credential_ids": []},
    )

    assert_error(response, 400, "At least one credential is required")


@pytest.mark.parametrize(
    ("enabled", "credential_id", "message"),
    [
        (True, "missing", "Credential not found for model discovery"),
        (False, "cred-a", "Credential is disabled for model discovery"),
    ],
)
def test_fetch_site_models_rejects_unavailable_credentials(
    client, admin_headers, enabled, credential_id, message
) -> None:
    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example/v1",
            "credentials": [
                {
                    "id": "cred-a",
                    "name": "primary",
                    "api_key": "upstream-secret",
                    "enabled": enabled,
                }
            ],
            "credential_ids": [credential_id],
        },
    )

    assert_error(response, 400, message)


def test_fetch_site_models_returns_bad_gateway_when_all_upstreams_fail(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    async def failing_fetch(_channel: Any) -> list[str]:
        raise HTTPException(status_code=503, detail="upstream unavailable")

    import lens_api.gateway.service.admin.sites as sites

    monkeypatch.setattr(sites, "_fetch_upstream_models", failing_fetch)

    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example/v1",
            "credentials": [
                {
                    "id": "cred-a",
                    "name": "primary",
                    "api_key": "upstream-secret",
                    "enabled": True,
                }
            ],
            "credential_ids": ["cred-a"],
        },
    )

    assert_error(response, 502, "Model discovery failed")


def test_test_site_model_returns_probe_result(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    async def fake_probe(**kwargs: Any) -> SiteModelTestResult:
        return SiteModelTestResult(
            success=True,
            status_code=200,
            latency_ms=8,
            model_name=kwargs["model_name"],
            credential_id=kwargs["credential_id"],
            output_text="pong",
        )

    import lens_api.gateway.service.admin.sites as sites

    monkeypatch.setattr(sites, "_call_site_model_probe_channel", fake_probe)

    response = client.post(
        "/api/admin/site-model-tests",
        headers=admin_headers,
        json=_model_test_payload(ProtocolKind.OPENAI_CHAT),
    )

    assert response.status_code == 200
    assert response.json()["output_text"] == "pong"


def test_test_site_model_returns_timeout_result(
    client,
    admin_headers,
    app_state,
    monkeypatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(60)
        return httpx.Response(200, json={}, request=request)

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    import lens_api.gateway.service.site_model_probe as probe

    monkeypatch.setattr(probe, "app_state", app_state)
    monkeypatch.setattr(probe, "_resolve_http_client", lambda _proxy: upstream_client)
    run_async(
        app_state.settings_repo.upsert_settings(
            [SettingItem(key=SETTING_FIRST_TOKEN_TIMEOUT_SECONDS, value="0.01")]
        )
    )

    try:
        response = client.post(
            "/api/admin/site-model-tests",
            headers=admin_headers,
            json=_model_test_payload(ProtocolKind.OPENAI_CHAT),
        )
    finally:
        run_async(upstream_client.aclose())

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["status_code"] == 504
    assert "timed out after 0.01s" in response.json()["error_message"]


def test_test_site_model_cancels_upstream_on_client_disconnect(monkeypatch) -> None:
    async def run_test() -> bool:
        probe_started = asyncio.Event()
        probe_cancelled = False

        async def hanging_probe(**_kwargs: Any) -> SiteModelTestResult:
            nonlocal probe_cancelled
            probe_started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                probe_cancelled = True
                raise

        async def receive() -> dict[str, str]:
            await probe_started.wait()
            return {"type": "http.disconnect"}

        import lens_api.gateway.service.admin.sites as sites

        monkeypatch.setattr(sites, "_call_site_model_probe_channel", hanging_probe)
        await sites.test_site_model(
            SiteModelTestRequest.model_validate(
                _model_test_payload(ProtocolKind.OPENAI_CHAT)
            ),
            Request({"type": "http"}, receive),
            None,
        )
        return probe_cancelled

    assert run_async(run_test()) is True


@pytest.mark.parametrize(
    ("protocol", "forbidden_fields"),
    [
        (ProtocolKind.OPENAI_EMBEDDING, ("stream",)),
        (ProtocolKind.OPENAI_IMAGE, ("stream",)),
        (ProtocolKind.RERANK, ("stream",)),
        (
            ProtocolKind.OPENAI_CHAT,
            ("max_tokens", "max_completion_tokens"),
        ),
    ],
)
def test_test_site_model_omits_unsupported_upstream_fields(
    client,
    admin_headers,
    monkeypatch,
    protocol: ProtocolKind,
    forbidden_fields: tuple[str, ...],
) -> None:
    captured_body: dict[str, Any] = {}

    async def fake_probe(**kwargs: Any) -> SiteModelTestResult:
        captured_body.update(kwargs["body"])
        return SiteModelTestResult(
            success=True,
            status_code=200,
            latency_ms=1,
            model_name=kwargs["model_name"],
            credential_id=kwargs["credential_id"],
        )

    import lens_api.gateway.service.admin.sites as sites

    monkeypatch.setattr(sites, "_call_site_model_probe_channel", fake_probe)

    response = client.post(
        "/api/admin/site-model-tests",
        headers=admin_headers,
        json=_model_test_payload(protocol),
    )

    assert response.status_code == 200
    assert all(field not in captured_body for field in forbidden_fields)


def test_test_site_model_rejects_non_object_success_payload(
    client,
    admin_headers,
    app_state,
    monkeypatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[], request=request)

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    import lens_api.gateway.service.site_model_probe as probe

    monkeypatch.setattr(probe, "app_state", app_state)
    monkeypatch.setattr(probe, "_resolve_http_client", lambda _proxy: upstream_client)
    try:
        response = client.post(
            "/api/admin/site-model-tests",
            headers=admin_headers,
            json=_model_test_payload(ProtocolKind.OPENAI_CHAT),
        )
    finally:
        run_async(upstream_client.aclose())

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["status_code"] == 502
    assert response.json()["error_message"] == (
        "Invalid upstream response: Expected JSON object"
    )


def test_sync_channel_models_uses_service_task(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    async def fake_sync(_state: Any, *, dry_run: bool) -> ChannelModelSyncResponse:
        return ChannelModelSyncResponse(dry_run=dry_run, synced_channel_count=2)

    import lens_api.gateway.service.model_sync as model_sync

    monkeypatch.setattr(model_sync, "sync_channel_models", fake_sync)

    response = client.post(
        "/api/admin/channel-model-sync",
        headers=admin_headers,
        json={"dry_run": False},
    )

    assert response.status_code == 200
    assert response.json()["synced_channel_count"] == 2
