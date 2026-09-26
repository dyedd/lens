from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from conftest import assert_error, run_async
from fastapi import HTTPException

from app.models.protocols import ProtocolKind
from app.models.settings import SettingItem
from app.models.site_model_test import SiteModelTestResult
from app.persistence.settings_keys import SETTING_FIRST_TOKEN_TIMEOUT_SECONDS


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

    import app.gateway.service.admin.sites as sites

    monkeypatch.setattr(sites, "fetch_upstream_models", fake_fetch)

    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example/v1",
            "headers": [],
            "credentials": [
                {
                    "id": "cred-a",
                    "name": "primary",
                    "api_key": "upstream-secret",
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


def test_fetch_site_models_rejects_missing_credentials(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example/v1",
            "headers": [],
            "credentials": [
                {
                    "id": "cred-a",
                    "name": "primary",
                    "api_key": "upstream-secret",
                }
            ],
            "credential_ids": ["missing"],
        },
    )

    assert_error(response, 400, "Credential not found for model discovery")


def test_fetch_site_models_returns_bad_gateway_when_all_upstreams_fail(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    async def failing_fetch(_channel: Any) -> list[str]:
        raise HTTPException(status_code=503, detail="upstream unavailable")

    import app.gateway.service.admin.sites as sites

    monkeypatch.setattr(sites, "fetch_upstream_models", failing_fetch)

    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example/v1",
            "headers": [],
            "credentials": [
                {
                    "id": "cred-a",
                    "name": "primary",
                    "api_key": "upstream-secret",
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

    import app.gateway.service.tasks.site_model_probe as probe

    monkeypatch.setattr(probe, "_call_site_model_probe_channel", fake_probe)

    response = client.post(
        "/api/admin/site-model-tests",
        headers=admin_headers,
        json=_model_test_payload(ProtocolKind.OPENAI_CHAT),
    )

    assert response.status_code == 200
    assert response.json()["output_text"] == "pong"


def test_test_site_model_returns_sanitized_probe_debug(
    client, admin_headers, app_state, monkeypatch
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer upstream-secret"
        return httpx.Response(
            200,
            headers={"content-type": "application/json", "x-request-id": "probe-1"},
            json={"choices": [{"message": {"content": "pong"}}]},
            request=request,
        )

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    import app.gateway.service.tasks.site_model_probe as probe

    monkeypatch.setattr(probe, "app_state", app_state)
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream_client)
    try:
        response = client.post(
            "/api/admin/site-model-tests",
            headers=admin_headers,
            json=_model_test_payload(ProtocolKind.OPENAI_CHAT),
        )
    finally:
        run_async(upstream_client.aclose())

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["debug"]["request"]["path"] == "/v1/chat/completions"
    assert result["debug"]["request"]["body"]["messages"] == [
        {"role": "user", "content": "ping"}
    ]
    assert result["debug"]["response"]["headers"]["x-request-id"] == "probe-1"
    assert "upstream-secret" not in response.text


def test_test_gemini_probe_debug_hides_query_key(
    client, admin_headers, app_state, monkeypatch
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["key"] == "upstream-secret"
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "OK"}]}}]},
            request=request,
        )

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    import app.gateway.service.tasks.site_model_probe as probe

    monkeypatch.setattr(probe, "app_state", app_state)
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream_client)
    try:
        response = client.post(
            "/api/admin/site-model-tests",
            headers=admin_headers,
            json=_model_test_payload(ProtocolKind.GEMINI),
        )
    finally:
        run_async(upstream_client.aclose())

    assert response.status_code == 200
    assert response.json()["debug"]["request"]["path"] == (
        "/v1beta/models/test-model:generateContent"
    )
    assert "upstream-secret" not in response.text


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
    import app.gateway.service.tasks.site_model_probe as probe

    monkeypatch.setattr(probe, "app_state", app_state)
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream_client)
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
    assert response.json()["debug"]["request"]["path"] == "/v1/chat/completions"


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

    import app.gateway.service.tasks.site_model_probe as probe

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
    import app.gateway.service.tasks.site_model_probe as probe

    monkeypatch.setattr(probe, "app_state", app_state)
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream_client)
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


def _model(
    model_name: str,
    *,
    credential_id: str = "cred-a",
    source: str = "synced",
    **fields: Any,
) -> dict[str, Any]:
    return {
        "credential_id": credential_id,
        "model_name": model_name,
        "enabled": True,
        "protocol": "openai_chat",
        "source": source,
        **fields,
    }


def _sync_site_payload(**site_fields: Any) -> dict[str, Any]:
    """Build a two-credential site whose upstream models sync automatically."""
    return {
        "name": "Multi-key Site",
        "model_sync_enabled": True,
        **site_fields,
        "base_urls": [{"id": "base-1", "url": "https://upstream.example/v1"}],
        "credentials": [
            {"id": "cred-a", "name": "key-a", "api_key": "secret-a"},
            {"id": "cred-b", "name": "key-b", "api_key": "secret-b"},
        ],
        "protocols": [
            {
                "id": "pc-1",
                "base_url_id": "base-1",
                "protocols": ["openai_chat"],
                "models": [_model("manual-only", source="manual")],
            }
        ],
    }


def _create_sync_site(client, admin_headers, payload: dict[str, Any]) -> str:
    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _patch_upstream_models(monkeypatch, fetch: Any) -> None:
    import app.gateway.service.tasks.model_sync as model_sync

    monkeypatch.setattr(model_sync, "fetch_upstream_models", fetch)


def _run_model_sync(client, admin_headers, **body: Any) -> dict[str, Any]:
    response = client.post(
        "/api/admin/channel-model-sync", headers=admin_headers, json=body
    )
    assert response.status_code == 200, response.text
    return response.json()


def _stored_models(client, admin_headers) -> set[tuple[str, str, str, bool]]:
    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    return {
        (
            model["credential_id"],
            model["model_name"],
            model["source"],
            model["upstream_missing"],
        )
        for model in site["protocols"][0]["models"]
    }


def test_channel_model_sync_adds_filtered_upstream_models_for_each_credential(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(model_sync_include="^gpt-", model_sync_exclude="-preview$"),
    )

    async def fake_fetch(channel: Any) -> list[str]:
        assert len(channel.keys) == 1
        return ["gpt-4o", "gpt-4o-preview", "claude-3-opus"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    result = _run_model_sync(client, admin_headers)

    assert {
        (item["credential_id"], item["status"], tuple(item["added"]))
        for item in result["items"]
    } == {
        ("cred-a", "updated", ("gpt-4o",)),
        ("cred-b", "updated", ("gpt-4o",)),
    }
    assert _stored_models(client, admin_headers) == {
        ("cred-a", "manual-only", "manual", False),
        ("cred-a", "gpt-4o", "synced", False),
        ("cred-b", "gpt-4o", "synced", False),
    }


def test_channel_model_sync_places_new_models_into_failover_groups(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(client, admin_headers, _sync_site_payload())

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    _run_model_sync(client, admin_headers)
    groups = client.get("/api/admin/model-groups", headers=admin_headers).json()

    assert {
        (
            group["name"],
            group["strategy"],
            tuple(group["match_models"]),
            tuple(sorted(item["credential_id"] for item in group["items"])),
        )
        for group in groups
    } == {
        ("manual-only", "failover", ("manual-only",), ("cred-a",)),
        ("gpt-4o", "failover", ("gpt-4o",), ("cred-a", "cred-b")),
    }


def test_channel_model_sync_flags_vanished_models_instead_of_deleting_them(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    payload = _sync_site_payload()
    payload["protocols"][0]["models"].append(_model("gpt-old"))
    _create_sync_site(client, admin_headers, payload)
    upstream_models = ["gpt-new"]

    async def fake_fetch(_channel: Any) -> list[str]:
        return list(upstream_models)

    _patch_upstream_models(monkeypatch, fake_fetch)

    flagged = _run_model_sync(client, admin_headers)
    flagged_models = _stored_models(client, admin_headers)
    upstream_models.append("gpt-old")
    restored = _run_model_sync(client, admin_headers)

    assert {
        (item["credential_id"], tuple(item["missing"])) for item in flagged["items"]
    } == {("cred-a", ("gpt-old",)), ("cred-b", ())}
    assert ("cred-a", "gpt-old", "synced", True) in flagged_models
    assert ("cred-a", "manual-only", "manual", False) in flagged_models
    assert {
        (item["credential_id"], tuple(item["restored"])) for item in restored["items"]
    } == {("cred-a", ("gpt-old",)), ("cred-b", ())}
    assert ("cred-a", "gpt-old", "synced", False) in _stored_models(
        client, admin_headers
    )


@pytest.mark.parametrize(
    "failed_catalog",
    [
        pytest.param(
            HTTPException(status_code=502, detail="credential failed"),
            id="upstream-error",
        ),
        pytest.param([], id="empty-catalog"),
    ],
)
def test_channel_model_sync_leaves_models_untouched_when_a_catalog_fails(
    client,
    admin_headers,
    monkeypatch,
    failed_catalog: Any,
) -> None:
    payload = _sync_site_payload()
    payload["protocols"][0]["models"].append(_model("gpt-old"))
    _create_sync_site(client, admin_headers, payload)

    async def fake_fetch(channel: Any) -> list[str]:
        if channel.keys[0].id != "cred-a":
            return ["gpt-new"]
        if isinstance(failed_catalog, Exception):
            raise failed_catalog
        return failed_catalog

    _patch_upstream_models(monkeypatch, fake_fetch)

    result = _run_model_sync(client, admin_headers)

    assert {(item["credential_id"], item["status"]) for item in result["items"]} == {
        ("cred-a", "failed"),
        ("cred-b", "updated"),
    }
    assert {
        model for model in _stored_models(client, admin_headers) if model[0] == "cred-a"
    } == {
        ("cred-a", "manual-only", "manual", False),
        ("cred-a", "gpt-old", "synced", False),
    }


@pytest.mark.parametrize(
    ("site_fields", "is_site_disabled", "sync_request"),
    [
        pytest.param({"model_sync_enabled": False}, False, {}, id="sync-disabled"),
        pytest.param({}, True, {}, id="site-disabled"),
        pytest.param({}, False, {"site_ids": ["other-site"]}, id="not-requested"),
    ],
)
def test_channel_model_sync_skips_sites_outside_its_scope(
    client,
    admin_headers,
    monkeypatch,
    site_fields: dict[str, Any],
    is_site_disabled: bool,
    sync_request: dict[str, Any],
) -> None:
    site_id = _create_sync_site(
        client, admin_headers, _sync_site_payload(**site_fields)
    )
    if is_site_disabled:
        disable_response = client.put(
            f"/api/admin/sites/{site_id}/enabled",
            headers=admin_headers,
            json={"enabled": False},
        )
        assert disable_response.status_code == 200, disable_response.text

    async def fail_fetch(_channel: Any) -> list[str]:
        raise AssertionError("skipped sites must not trigger model discovery")

    _patch_upstream_models(monkeypatch, fail_fetch)

    result = _run_model_sync(client, admin_headers, **sync_request)

    assert result["items"] == []


def test_site_save_keeps_upstream_missing_flag_only_on_synced_models(
    client,
    admin_headers,
) -> None:
    payload = _sync_site_payload()
    payload["protocols"][0]["models"] = [
        _model("gpt-gone", upstream_missing=True),
        _model("kept-by-admin", source="manual", upstream_missing=True),
    ]

    _create_sync_site(client, admin_headers, payload)

    assert _stored_models(client, admin_headers) == {
        ("cred-a", "gpt-gone", "synced", True),
        ("cred-a", "kept-by-admin", "manual", False),
    }


def test_site_rejects_duplicate_models_across_sources(
    client,
    admin_headers,
) -> None:
    payload = _sync_site_payload()
    payload["protocols"][0]["models"].append(_model("manual-only"))

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert_error(response, 400, "Duplicate model in protocol config")


def test_channel_model_sync_never_mixes_automatic_and_fixed_protocols(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    payload = _sync_site_payload()
    payload["protocols"][0]["models"] = [
        _model("auto-model", source="manual", protocol="auto"),
        _model("fixed-model", source="manual"),
    ]
    _create_sync_site(client, admin_headers, payload)

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["auto-model", "fixed-model", "new-model"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    _run_model_sync(client, admin_headers)

    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    protocols_by_model: dict[tuple[str, str], set[str]] = {}
    for model in site["protocols"][0]["models"]:
        protocols_by_model.setdefault(
            (model["credential_id"], model["model_name"]), set()
        ).add(model["protocol"])
    assert protocols_by_model == {
        ("cred-a", "auto-model"): {"auto"},
        ("cred-a", "fixed-model"): {"openai_chat"},
        ("cred-a", "new-model"): {"auto"},
        ("cred-b", "auto-model"): {"auto"},
        ("cred-b", "fixed-model"): {"auto"},
        ("cred-b", "new-model"): {"auto"},
    }
