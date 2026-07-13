from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from conftest import assert_error, openai_chat_channel_id, seed_request_log
from lens_api.models import ChannelModelSyncResponse, SiteModelTestResult


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
        json={
            "protocol": "openai_chat",
            "base_url": "https://upstream.example/v1",
            "credential": {
                "id": "cred-a",
                "name": "primary",
                "api_key": "upstream-secret",
            },
            "model_name": "gpt-4o",
            "prompt": "ping",
        },
    )

    assert response.status_code == 200
    assert response.json()["output_text"] == "pong"


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
