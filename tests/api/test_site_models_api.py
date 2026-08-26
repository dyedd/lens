from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import HTTPException

from conftest import assert_error, run_async
from lens_api.models import ProtocolKind, SiteModelTestResult
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

    import lens_api.gateway.service.site_model_probe as probe

    monkeypatch.setattr(probe, "_call_site_model_probe_channel", fake_probe)

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

    import lens_api.gateway.service.site_model_probe as probe

    monkeypatch.setattr(probe, "_call_site_model_probe_channel", fake_probe)

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


def _sync_target(model_name: str, credential_id: str = "cred-a") -> dict[str, str]:
    return {
        "credential_id": credential_id,
        "model_name": model_name,
        "protocol": "openai_chat",
    }


def test_create_site_persists_exact_sync_targets(
    client,
    admin_headers,
) -> None:
    payload = _auto_sync_site_payload(seed_synced=True)

    response = client.post(
        "/api/admin/sites",
        headers=admin_headers,
        json=payload,
    )

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["protocols"][0]["sync_targets"] == [
        _sync_target("gpt-cred-a"),
        _sync_target("gpt-cred-b", "cred-b"),
    ]


def _auto_sync_site_payload(seed_synced: bool = False) -> dict[str, Any]:
    """Builds a two-credential site payload.

    ``seed_synced`` materializes the first exact target before synchronization.
    """
    models: list[dict[str, Any]] = [
        {
            "credential_id": "cred-a",
            "model_name": "manual-only",
            "enabled": True,
            "protocol": "openai_chat",
            "source": "manual",
        }
    ]
    if seed_synced:
        models.append(
            {
                "credential_id": "cred-a",
                "model_name": "gpt-cred-a",
                "enabled": True,
                "protocol": "openai_chat",
                "source": "synced",
            }
        )
    return {
        "name": "Multi-key Site",
        "base_urls": [
            {
                "id": "base-1",
                "url": "https://upstream.example/v1",
                "name": "primary",
                "enabled": True,
                "supported_protocols": ["openai_chat"],
            }
        ],
        "credentials": [
            {
                "id": "cred-a",
                "name": "key-a",
                "api_key": "secret-a",
                "enabled": True,
            },
            {
                "id": "cred-b",
                "name": "key-b",
                "api_key": "secret-b",
                "enabled": True,
            },
        ],
        "protocols": [
            {
                "id": "pc-1",
                "name": "primary",
                "protocols": ["openai_chat"],
                "enabled": True,
                "base_url_id": "base-1",
                "credential_ids": ["cred-a", "cred-b"],
                "sync_targets": [
                    _sync_target("gpt-cred-a"),
                    _sync_target("gpt-cred-b", "cred-b"),
                ],
                "models": models,
            }
        ],
    }


def test_channel_model_sync_preserves_manual_models_and_syncs_each_credential(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    create_response = client.post(
        "/api/admin/sites",
        headers=admin_headers,
        json=_auto_sync_site_payload(seed_synced=True),
    )
    assert create_response.status_code == 201, create_response.text

    async def fake_fetch(channel: Any, *, apply_match_regex: bool = True) -> list[str]:
        assert len(channel.keys) == 1
        return [f"gpt-{channel.keys[0].id}"]

    import lens_api.gateway.service.model_sync as model_sync

    monkeypatch.setattr(model_sync, "_fetch_upstream_models", fake_fetch)
    response = client.post(
        "/api/admin/channel-model-sync",
        headers=admin_headers,
        json={"dry_run": False},
    )

    assert response.status_code == 200, response.text
    assert response.json()["eligible_target_count"] == 2
    stored_models = client.get("/api/admin/sites", headers=admin_headers).json()[0][
        "protocols"
    ][0]["models"]
    assert {
        (model["credential_id"], model["model_name"], model["source"])
        for model in stored_models
    } == {
        ("cred-a", "manual-only", "manual"),
        ("cred-a", "gpt-cred-a", "synced"),
        ("cred-b", "gpt-cred-b", "synced"),
    }


def test_channel_model_sync_removes_only_stale_synced_models(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    payload = _auto_sync_site_payload()
    payload["protocols"][0]["models"].extend(
        [
            {
                "credential_id": "cred-a",
                "model_name": "gpt-stale",
                "enabled": True,
                "protocol": "openai_chat",
                "source": "synced",
            },
            {
                "credential_id": "cred-b",
                "model_name": "manual-stale",
                "enabled": True,
                "protocol": "openai_chat",
                "source": "manual",
            },
        ]
    )
    payload["protocols"][0]["sync_targets"].append(_sync_target("gpt-stale"))
    create_response = client.post(
        "/api/admin/sites",
        headers=admin_headers,
        json=payload,
    )
    assert create_response.status_code == 201, create_response.text

    async def fake_fetch(channel: Any, *, apply_match_regex: bool = True) -> list[str]:
        return [f"gpt-{channel.keys[0].id}", "claude-3-opus"]

    import lens_api.gateway.service.model_sync as model_sync

    monkeypatch.setattr(model_sync, "_fetch_upstream_models", fake_fetch)
    response = client.post(
        "/api/admin/channel-model-sync",
        headers=admin_headers,
        json={"dry_run": False},
    )

    assert response.status_code == 200, response.text
    stored_models = client.get("/api/admin/sites", headers=admin_headers).json()[0][
        "protocols"
    ][0]["models"]
    by_source: dict[str, set[str]] = {"manual": set(), "synced": set()}
    for model in stored_models:
        by_source[model["source"]].add(model["model_name"])
    # The durable target, not the upstream listing, decides what is synced.
    assert by_source["synced"] == {"gpt-cred-a", "gpt-cred-b"}
    assert by_source["manual"] == {"manual-only", "manual-stale"}


def test_site_rejects_duplicate_models_for_the_same_sync_target(
    client,
    admin_headers,
) -> None:
    payload = _auto_sync_site_payload()
    payload["protocols"][0]["models"].append(
        {
            "credential_id": "cred-a",
            "model_name": "manual-only",
            "enabled": True,
            "protocol": "openai_chat",
            "source": "synced",
        }
    )
    response = client.post(
        "/api/admin/sites",
        headers=admin_headers,
        json=payload,
    )

    assert_error(response, 400, "Duplicate model in protocol config")


def test_channel_model_sync_isolates_target_failures(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    create_response = client.post(
        "/api/admin/sites",
        headers=admin_headers,
        json=_auto_sync_site_payload(seed_synced=True),
    )
    assert create_response.status_code == 201, create_response.text

    async def fake_fetch(channel: Any, *, apply_match_regex: bool = True) -> list[str]:
        credential_id = channel.keys[0].id
        if credential_id == "cred-a":
            raise HTTPException(status_code=502, detail="credential failed")
        return ["gpt-cred-b"]

    import lens_api.gateway.service.model_sync as model_sync

    monkeypatch.setattr(model_sync, "_fetch_upstream_models", fake_fetch)
    response = client.post(
        "/api/admin/channel-model-sync",
        headers=admin_headers,
        json={"dry_run": False},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["failed_target_count"] == 1
    assert result["updated_target_count"] == 1
    assert {(item["credential_id"], item["status"]) for item in result["items"]} == {
        ("cred-a", "failed"),
        ("cred-b", "updated"),
    }
    stored_models = client.get("/api/admin/sites", headers=admin_headers).json()[0][
        "protocols"
    ][0]["models"]
    assert {
        (model["credential_id"], model["model_name"], model["source"])
        for model in stored_models
    } == {
        ("cred-a", "manual-only", "manual"),
        ("cred-a", "gpt-cred-a", "synced"),
        ("cred-b", "gpt-cred-b", "synced"),
    }


def test_channel_model_sync_dry_run_does_not_write_models(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    payload = _auto_sync_site_payload()
    payload["protocols"][0]["models"].append(
        {
            "credential_id": "cred-a",
            "model_name": "gpt-old",
            "enabled": True,
            "protocol": "openai_chat",
            "source": "synced",
        }
    )
    payload["protocols"][0]["sync_targets"].append(_sync_target("gpt-old"))
    create_response = client.post(
        "/api/admin/sites", headers=admin_headers, json=payload
    )
    assert create_response.status_code == 201, create_response.text

    async def fake_fetch(channel: Any, *, apply_match_regex: bool = True) -> list[str]:
        return [f"gpt-new-{channel.keys[0].id}"]

    import lens_api.gateway.service.model_sync as model_sync

    monkeypatch.setattr(model_sync, "_fetch_upstream_models", fake_fetch)
    response = client.post(
        "/api/admin/channel-model-sync",
        headers=admin_headers,
        json={"dry_run": True},
    )

    assert response.status_code == 200, response.text
    assert response.json()["updated_target_count"] == 1
    stored_models = client.get("/api/admin/sites", headers=admin_headers).json()[0][
        "protocols"
    ][0]["models"]
    assert {model["model_name"] for model in stored_models} == {
        "manual-only",
        "gpt-old",
    }


def test_channel_model_sync_does_not_report_group_changes_that_failed(
    client,
    admin_headers,
    app_state,
    monkeypatch,
) -> None:
    create_response = client.post(
        "/api/admin/sites",
        headers=admin_headers,
        json=_auto_sync_site_payload(seed_synced=True),
    )
    assert create_response.status_code == 201, create_response.text
    group_response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "gpt models",
            "sync_filter_mode": "contains",
            "sync_filter_query": "gpt-",
        },
    )
    assert group_response.status_code == 201, group_response.text

    async def fake_fetch(channel: Any, *, apply_match_regex: bool = True) -> list[str]:
        return [f"gpt-{channel.keys[0].id}"]

    async def fail_group_update(_payload: Any) -> None:
        raise RuntimeError("group update failed")

    import lens_api.gateway.service.model_sync as model_sync

    monkeypatch.setattr(model_sync, "_fetch_upstream_models", fake_fetch)
    monkeypatch.setattr(
        app_state.group_repo,
        "ensure_groups_from_site",
        fail_group_update,
    )
    response = client.post(
        "/api/admin/channel-model-sync",
        headers=admin_headers,
        json={"dry_run": False},
    )

    assert response.status_code == 200, response.text
    changed_items = [
        item for item in response.json()["items"] if item["status"] == "updated"
    ]
    assert len(changed_items) == 1
    assert all(item["group_added"] == [] for item in changed_items)
    assert all("model group update failed" in item["warning"] for item in changed_items)


def test_channel_model_sync_reports_applied_group_changes(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    create_response = client.post(
        "/api/admin/sites",
        headers=admin_headers,
        json=_auto_sync_site_payload(seed_synced=True),
    )
    assert create_response.status_code == 201, create_response.text
    group_response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "gpt models",
            "sync_filter_mode": "contains",
            "sync_filter_query": "gpt-",
        },
    )
    assert group_response.status_code == 201, group_response.text

    async def fake_fetch(channel: Any, *, apply_match_regex: bool = True) -> list[str]:
        return [f"gpt-{channel.keys[0].id}"]

    import lens_api.gateway.service.model_sync as model_sync

    monkeypatch.setattr(model_sync, "_fetch_upstream_models", fake_fetch)
    response = client.post(
        "/api/admin/channel-model-sync",
        headers=admin_headers,
        json={"dry_run": False},
    )

    assert response.status_code == 200, response.text
    assert {
        (item["credential_id"], change["group_name"], change["model_name"])
        for item in response.json()["items"]
        for change in item["group_added"]
    } == {
        ("cred-b", "gpt models", "gpt-cred-b"),
    }
    group = client.get("/api/admin/model-groups", headers=admin_headers).json()[0]
    assert {item["model_name"] for item in group["items"]} == {
        "gpt-cred-b",
    }


@pytest.mark.parametrize(
    "disabled_resource", ["site", "base_url", "config", "credential"]
)
def test_channel_model_sync_skips_disabled_resources_without_fetching(
    client,
    admin_headers,
    monkeypatch,
    disabled_resource: str,
) -> None:
    payload = _auto_sync_site_payload(seed_synced=True)
    if disabled_resource == "base_url":
        payload["base_urls"][0]["enabled"] = False
    elif disabled_resource == "config":
        payload["protocols"][0]["enabled"] = False
    elif disabled_resource == "credential":
        for credential in payload["credentials"]:
            credential["enabled"] = False
    create_response = client.post(
        "/api/admin/sites", headers=admin_headers, json=payload
    )
    assert create_response.status_code == 201, create_response.text
    if disabled_resource == "site":
        disable_response = client.put(
            f"/api/admin/sites/{create_response.json()['id']}/enabled",
            headers=admin_headers,
            json={"enabled": False},
        )
        assert disable_response.status_code == 200, disable_response.text

    async def fail_fetch(_channel: Any, *, apply_match_regex: bool = True) -> list[str]:
        raise AssertionError("disabled resources must not trigger model discovery")

    import lens_api.gateway.service.model_sync as model_sync

    monkeypatch.setattr(model_sync, "_fetch_upstream_models", fail_fetch)
    response = client.post(
        "/api/admin/channel-model-sync",
        headers=admin_headers,
        json={"dry_run": False},
    )

    assert response.status_code == 200, response.text
    assert response.json()["eligible_target_count"] == 0


def test_synced_models_require_explicit_sync_targets(
    client,
    admin_headers,
) -> None:
    payload = _auto_sync_site_payload()
    payload["protocols"][0]["sync_targets"] = []
    payload["protocols"][0]["models"] = [
        {
            "credential_id": "cred-a",
            "model_name": "manual-only",
            "enabled": True,
            "protocol": "openai_chat",
            "source": "manual",
        }
    ]

    create_response = client.post(
        "/api/admin/sites", headers=admin_headers, json=payload
    )

    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["protocols"][0]["sync_targets"] == []

    payload["protocols"][0]["models"].append(
        {
            "credential_id": "cred-a",
            "model_name": "gpt-synced",
            "enabled": True,
            "protocol": "openai_chat",
            "source": "synced",
        }
    )
    update_response = client.put(
        f"/api/admin/sites/{create_response.json()['id']}",
        headers=admin_headers,
        json=payload,
    )

    assert_error(update_response, 400, "Synced model is missing its sync target")

    payload["protocols"][0]["sync_targets"] = [_sync_target("gpt-synced")]
    update_response = client.put(
        f"/api/admin/sites/{create_response.json()['id']}",
        headers=admin_headers,
        json=payload,
    )

    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()["protocols"][0]
    assert updated["sync_targets"] == [_sync_target("gpt-synced")]
    assert {model["model_name"]: model["source"] for model in updated["models"]} == {
        "manual-only": "manual",
        "gpt-synced": "synced",
    }


def test_channel_model_sync_skips_configs_without_synced_models(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    payload = _auto_sync_site_payload()
    payload["protocols"][0]["sync_targets"] = []
    payload["protocols"][0]["models"] = [
        {
            "credential_id": "cred-a",
            "model_name": "manual-only",
            "enabled": True,
            "protocol": "openai_chat",
            "source": "manual",
        }
    ]
    create_response = client.post(
        "/api/admin/sites", headers=admin_headers, json=payload
    )
    assert create_response.status_code == 201, create_response.text

    async def fail_fetch(_channel: Any, *, apply_match_regex: bool = True) -> list[str]:
        raise AssertionError("upstream should not be queried without synced models")

    import lens_api.gateway.service.model_sync as model_sync

    monkeypatch.setattr(model_sync, "_fetch_upstream_models", fail_fetch)
    response = client.post(
        "/api/admin/channel-model-sync",
        headers=admin_headers,
        json={"dry_run": False},
    )

    assert response.status_code == 200, response.text
    assert response.json()["eligible_target_count"] == 0


def test_sync_target_is_retained_when_upstream_temporarily_drops_it(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    payload = _auto_sync_site_payload()
    payload["protocols"][0]["credential_ids"] = ["cred-a"]
    payload["protocols"][0]["sync_targets"] = []
    payload["protocols"][0]["models"] = [
        {
            "credential_id": "cred-a",
            "model_name": "gpt-pinned",
            "enabled": True,
            "protocol": "openai_chat",
            "source": "manual",
        }
    ]
    create_response = client.post(
        "/api/admin/sites", headers=admin_headers, json=payload
    )
    assert create_response.status_code == 201, create_response.text
    site_id = create_response.json()["id"]

    payload["protocols"][0]["models"][0]["source"] = "synced"
    payload["protocols"][0]["sync_targets"] = [_sync_target("gpt-pinned")]
    update_response = client.put(
        f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
    )
    assert update_response.status_code == 200, update_response.text

    async def fake_fetch(_channel: Any, *, apply_match_regex: bool = True) -> list[str]:
        return []

    import lens_api.gateway.service.model_sync as model_sync

    monkeypatch.setattr(model_sync, "_fetch_upstream_models", fake_fetch)
    response = client.post(
        "/api/admin/channel-model-sync",
        headers=admin_headers,
        json={"dry_run": False},
    )

    assert response.status_code == 200, response.text
    assert response.json()["eligible_target_count"] == 1
    stored = client.get("/api/admin/sites", headers=admin_headers).json()[0][
        "protocols"
    ][0]
    assert stored["models"] == []
    assert stored["sync_targets"] == [_sync_target("gpt-pinned")]

    async def restored_fetch(_channel: Any) -> list[str]:
        return ["gpt-pinned"]

    monkeypatch.setattr(model_sync, "_fetch_upstream_models", restored_fetch)
    restore_response = client.post(
        "/api/admin/channel-model-sync",
        headers=admin_headers,
        json={"dry_run": False},
    )
    assert restore_response.status_code == 200, restore_response.text
    restored = client.get("/api/admin/sites", headers=admin_headers).json()[0][
        "protocols"
    ][0]
    assert {model["model_name"]: model["source"] for model in restored["models"]} == {
        "gpt-pinned": "synced"
    }
