from __future__ import annotations

import asyncio
import json
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
    from app.gateway.service.tasks.model_discovery import UpstreamModel

    async def fake_fetch(channel: Any) -> list[UpstreamModel]:
        assert channel.keys[0].id == "cred-a"
        return [
            UpstreamModel(name="gpt-4o", context_window=128_000),
            UpstreamModel(name="gpt-4o-mini"),
        ]

    import app.gateway.service.tasks.model_discovery as model_discovery

    monkeypatch.setattr(model_discovery, "fetch_upstream_models", fake_fetch)

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
    assert [
        (item["model_name"], item["context_window"]) for item in response.json()
    ] == [("gpt-4o", 128_000), ("gpt-4o-mini", None)]


@pytest.mark.parametrize(
    ("protocol", "path", "expected_params", "expected_headers", "upstream_body"),
    [
        pytest.param(
            "anthropic",
            "/v1/models",
            {"limit": "1000"},
            {"x-api-key": "upstream-secret", "anthropic-version": "2023-06-01"},
            {
                "data": [
                    {"id": "model-a", "max_input_tokens": 200_000},
                    {"id": "model-b"},
                ]
            },
            id="anthropic",
        ),
        pytest.param(
            "gemini",
            "/v1beta/models",
            {"key": "upstream-secret", "pageSize": "1000"},
            {"x-goog-api-key": "upstream-secret"},
            {
                "models": [
                    {"name": "models/model-a", "inputTokenLimit": 200_000},
                    {"name": "models/model-b"},
                ]
            },
            id="gemini",
        ),
    ],
)
def test_fetch_site_models_uses_protocol_native_model_list(
    client,
    admin_headers,
    monkeypatch,
    protocol,
    path,
    expected_params,
    expected_headers,
    upstream_body,
) -> None:
    import app.gateway.service.tasks.model_discovery as model_discovery

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=upstream_body)

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        model_discovery, "resolve_http_client", lambda _proxy: upstream_client
    )

    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example",
            "protocol": protocol,
            "credentials": [
                {"id": "cred-a", "name": "primary", "api_key": "upstream-secret"}
            ],
            "credential_ids": ["cred-a"],
        },
    )

    assert response.status_code == 200, response.text
    assert {item["model_name"]: item["context_window"] for item in response.json()} == {
        "model-a": 200_000,
        "model-b": None,
    }
    request = captured[0]
    assert request.url.path == path
    assert dict(request.url.params) == expected_params
    assert "authorization" not in request.headers
    for name, value in expected_headers.items():
        assert request.headers[name] == value


def test_fetch_site_models_falls_back_to_a_native_model_list(
    client, admin_headers, monkeypatch
) -> None:
    import app.gateway.service.tasks.model_discovery as model_discovery

    def handler(request: httpx.Request) -> httpx.Response:
        if "authorization" in request.headers:
            return httpx.Response(401, json={"error": {"message": "bad key"}})
        return httpx.Response(200, json={"data": [{"id": "claude-sonnet-4-5"}]})

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        model_discovery, "resolve_http_client", lambda _proxy: upstream_client
    )

    response = client.post(
        "/api/admin/site-model-discoveries",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example",
            "credentials": [{"id": "cred-a", "name": "primary", "api_key": "sk-test"}],
            "credential_ids": ["cred-a"],
        },
    )

    assert response.status_code == 200, response.text
    assert [item["model_name"] for item in response.json()] == ["claude-sonnet-4-5"]


def test_detect_site_model_protocols_probes_only_open_chat_models(
    client, admin_headers, monkeypatch
) -> None:
    import app.gateway.service.tasks.model_discovery as model_discovery
    import app.gateway.service.tasks.site_model_probe as probe

    probes: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "deepseek-chat", "supported_endpoint_types": ["openai"]},
                        {"id": "gpt-5"},
                        {"id": "claude-sonnet-4-5"},
                        {"id": "text-embedding-3-small"},
                        {"id": "mystery-model"},
                    ]
                },
            )
        model = json.loads(request.content)["model"]
        probes.append((model, request.url.path))
        if model == "mystery-model":
            return httpx.Response(404, json={"error": {"message": "no route"}})
        if request.url.path == "/v1/messages":
            return httpx.Response(
                200, json={"content": [{"type": "text", "text": "hello"}]}
            )
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(
                200, json={"choices": [{"message": {"content": "hello"}}]}
            )
        return httpx.Response(404, json={"error": {"message": "no route"}})

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        model_discovery, "resolve_http_client", lambda _proxy: upstream_client
    )
    monkeypatch.setattr(probe, "resolve_http_client", lambda _proxy: upstream_client)

    response = client.post(
        "/api/admin/site-model-protocol-detections",
        headers=admin_headers,
        json={
            "base_url": "https://upstream.example",
            "credential": {"id": "cred-a", "api_key": "sk-test"},
            "model_names": [
                "deepseek-chat",
                "gpt-5",
                "claude-sonnet-4-5",
                "text-embedding-3-small",
                "mystery-model",
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert {item["model_name"]: item["protocol"] for item in response.json()} == {
        "deepseek-chat": "openai_chat",
        "gpt-5": "openai_chat",
        "claude-sonnet-4-5": "anthropic",
        "text-embedding-3-small": "openai_embedding",
        "mystery-model": None,
    }
    assert {model for model, _path in probes} == {
        "gpt-5",
        "claude-sonnet-4-5",
        "mystery-model",
    }
    assert [path for model, path in probes if model == "gpt-5"] == [
        "/v1/responses",
        "/v1/chat/completions",
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

    import app.gateway.service.tasks.model_discovery as model_discovery

    monkeypatch.setattr(model_discovery, "fetch_upstream_models", failing_fetch)

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


def test_test_gemini_probe_debug_hides_api_key(
    client, admin_headers, app_state, monkeypatch
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1beta/interactions")
        assert request.headers["x-goog-api-key"] == "upstream-secret"
        return httpx.Response(
            200,
            json={
                "id": "interaction_1",
                "object": "interaction",
                "model": "test-model",
                "status": "completed",
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": "OK"}],
                    }
                ],
            },
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
    assert response.json()["debug"]["request"]["path"] == "/v1beta/interactions"
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
    **fields: Any,
) -> dict[str, Any]:
    return {
        "credential_id": credential_id,
        "model_name": model_name,
        "enabled": True,
        "protocol": "openai_chat",
        **fields,
    }


def _sync_site_payload(
    *,
    models: list[dict[str, Any]] | None = None,
    patterns: dict[str, str] | None = None,
    **site_fields: Any,
) -> dict[str, Any]:
    """Build a two-credential site with stored models and per-key filters."""
    filters = patterns or {}
    return {
        "name": "Multi-key Site",
        **site_fields,
        "base_urls": [{"id": "base-1", "url": "https://upstream.example/v1"}],
        "credentials": [
            {
                "id": "cred-a",
                "name": "key-a",
                "api_key": "secret-a",
                "model_pattern": filters.get("cred-a", ""),
            },
            {
                "id": "cred-b",
                "name": "key-b",
                "api_key": "secret-b",
                "model_pattern": filters.get("cred-b", ""),
            },
        ],
        "protocols": [
            {
                "id": "pc-1",
                "base_url_id": "base-1",
                "protocols": ["openai_chat"],
                "models": list(models or []),
            }
        ],
    }


def _create_sync_site(client, admin_headers, payload: dict[str, Any]) -> str:
    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _patch_upstream_models(monkeypatch, fetch: Any) -> None:
    import app.gateway.service.tasks.model_sync as model_sync
    from app.gateway.service.tasks.model_discovery import UpstreamModel

    async def fetch_models(channel: Any) -> list[UpstreamModel]:
        return [
            item if isinstance(item, UpstreamModel) else UpstreamModel(name=item)
            for item in await fetch(channel)
        ]

    monkeypatch.setattr(model_sync, "fetch_upstream_models", fetch_models)


def _run_model_sync(client, admin_headers, **body: Any) -> dict[str, Any]:
    response = client.post(
        "/api/admin/channel-model-sync", headers=admin_headers, json=body
    )
    assert response.status_code == 200, response.text
    return response.json()


def _stored_models(client, admin_headers) -> set[tuple[str, str]]:
    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    return {
        (model["credential_id"], model["model_name"])
        for model in site["protocols"][0]["models"]
    }


def _added_names(result: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    return {item["credential_id"]: tuple(item["added"]) for item in result["items"]}


def test_channel_model_sync_keeps_manual_models_when_the_filter_is_empty(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(models=[_model("manual-only")]),
    )

    async def fail_fetch(_channel: Any) -> list[str]:
        raise AssertionError("empty filters must not fetch or sync the catalog")

    _patch_upstream_models(monkeypatch, fail_fetch)

    result = _run_model_sync(client, admin_headers)
    groups = client.get("/api/admin/model-groups", headers=admin_headers).json()

    assert {item["status"] for item in result["items"]} == {"unchanged"}
    assert _stored_models(client, admin_headers) == {
        ("cred-a", "manual-only"),
    }
    assert [group["name"] for group in groups] == ["manual-only"]


def test_channel_model_sync_keeps_only_models_matching_the_key_filter(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "^gpt-4.*", "cred-b": "*"}),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o", "gpt-4o-mini", "claude-3-opus"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    result = _run_model_sync(client, admin_headers)

    assert _added_names(result)["cred-a"] == ("gpt-4o", "gpt-4o-mini")
    assert _stored_models(client, admin_headers) == {
        ("cred-a", "gpt-4o"),
        ("cred-a", "gpt-4o-mini"),
        ("cred-b", "gpt-4o"),
        ("cred-b", "gpt-4o-mini"),
        ("cred-b", "claude-3-opus"),
    }


def test_channel_model_sync_matches_whole_names_only(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "gpt-4"}),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4", "gpt-4o", "gpt-4o-mini"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    _run_model_sync(client, admin_headers)

    # ``gpt-4`` is a whole name, so its longer siblings stay out.
    assert {
        name
        for credential_id, name in _stored_models(client, admin_headers)
        if credential_id == "cred-a"
    } == {"gpt-4"}


def test_channel_model_sync_treats_dots_in_literal_names_as_text(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "claude-3.5-sonnet"}),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["claude-3.5-sonnet", "claude-3x5-sonnet"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    _run_model_sync(client, admin_headers)

    assert {
        name
        for credential_id, name in _stored_models(client, admin_headers)
        if credential_id == "cred-a"
    } == {"claude-3.5-sonnet"}


def test_channel_model_sync_wildcard_filter_takes_every_model(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "*", "cred-b": "^none$"}),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o", "claude-3-opus"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    _run_model_sync(client, admin_headers)

    assert _stored_models(client, admin_headers) == {
        ("cred-a", "gpt-4o"),
        ("cred-a", "claude-3-opus"),
    }


def test_channel_model_sync_stores_a_protocol_per_new_model(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    from app.gateway.service.tasks.model_discovery import UpstreamModel

    _create_sync_site(
        client, admin_headers, _sync_site_payload(patterns={"cred-a": "*"})
    )

    async def fake_fetch(_channel: Any) -> list[UpstreamModel]:
        return [
            UpstreamModel(name="gpt-4o"),
            UpstreamModel(name="text-embedding-3-small"),
            UpstreamModel(
                name="claude-sonnet-4-5",
                protocols=(ProtocolKind.OPENAI_CHAT, ProtocolKind.ANTHROPIC),
            ),
        ]

    _patch_upstream_models(monkeypatch, fake_fetch)

    _run_model_sync(client, admin_headers)
    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]

    assert {
        (model["model_name"], model["protocol"])
        for model in site["protocols"][0]["models"]
    } == {
        ("gpt-4o", "openai_chat"),
        ("text-embedding-3-small", "openai_embedding"),
        ("claude-sonnet-4-5", "anthropic"),
    }


@pytest.mark.parametrize("china_mode", ["shared", "owned", "absent"])
def test_multi_url_models_use_one_matching_endpoint_through_save_and_sync(
    client,
    admin_headers,
    monkeypatch,
    china_mode,
) -> None:
    import app.gateway.service.tasks.model_discovery as discovery

    payload = _sync_site_payload(patterns={"cred-a": "*"})
    payload["credentials"] = payload["credentials"][:1]
    payload["base_urls"] = [
        {"id": "main", "kind": "default", "url": "https://main.example/v1"},
        {"id": "china", "kind": "china", "url": "https://china.example/v1"},
        {"id": "claude", "kind": "anthropic", "url": "https://claude.example/v1"},
    ]
    payload["protocols"] = [
        {
            "id": "pc-main",
            "base_url_id": "main",
            "protocols": ["openai_chat", "anthropic"],
            "models": [
                _model("gpt-4o"),
                _model("claude-sonnet-4-5", protocol="anthropic"),
            ],
        },
        {
            "id": "pc-china",
            "base_url_id": "china",
            "protocols": ["openai_chat"],
            "models": [_model("gpt-4o")],
        },
        {
            "id": "pc-claude",
            "base_url_id": "claude",
            "protocols": ["anthropic"],
            "models": [_model("claude-sonnet-4-5", protocol="anthropic")],
        },
    ]
    if china_mode == "owned":
        payload["credentials"].append(
            {
                "id": "cred-china",
                "name": "china-key",
                "api_key": "secret-china",
                "base_url_id": "china",
                "model_pattern": "*",
            }
        )
        payload["protocols"][1]["models"][0]["credential_id"] = "cred-china"
    elif china_mode == "absent":
        payload["base_urls"] = [
            url for url in payload["base_urls"] if url["id"] != "china"
        ]
        payload["protocols"] = [
            config
            for config in payload["protocols"]
            if config["base_url_id"] != "china"
        ]
    site_id = _create_sync_site(client, admin_headers, payload)
    fetched: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        fetched.append(request.url.host)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gpt-4o", "supported_endpoint_types": ["openai"]},
                    {
                        "id": "claude-sonnet-4-5",
                        "supported_endpoint_types": ["anthropic"],
                    },
                    {"id": "text-embedding-3-small"},
                ]
            },
        )

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(discovery, "resolve_http_client", lambda _proxy: upstream)

    def stored() -> dict[str, set[tuple[str, str]]]:
        site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
        return {
            config["base_url_id"]: {
                (model["model_name"], model["protocol"]) for model in config["models"]
            }
            for config in site["protocols"]
        }

    try:
        expected = {
            "main": set() if china_mode == "shared" else {("gpt-4o", "openai_chat")},
            "claude": {("claude-sonnet-4-5", "anthropic")},
        }
        if china_mode != "absent":
            expected["china"] = {("gpt-4o", "openai_chat")}
        assert stored() == expected
        for url_id in (
            ["china"]
            if china_mode == "shared"
            else ["main", "china"]
            if china_mode == "owned"
            else ["main"]
        ):
            expected[url_id].add(("text-embedding-3-small", "openai_embedding"))
        if china_mode == "owned":
            expected["china"].add(("claude-sonnet-4-5", "anthropic"))
        for _ in range(2):
            result = _run_model_sync(client, admin_headers, site_ids=[site_id])
            assert {item["status"] for item in result["items"]} <= {
                "updated",
                "unchanged",
            }
            assert stored() == expected
        assert fetched.count("china.example") == (0 if china_mode == "absent" else 2)
        assert fetched.count("main.example") == (0 if china_mode == "shared" else 2)
        assert "claude.example" not in fetched
        groups = client.post(
            "/api/admin/model-group-candidates",
            headers=admin_headers,
            json={"items": []},
        )
        assert groups.status_code == 200, groups.text
        expected_names = [
            "claude-sonnet-4-5",
            "gpt-4o",
            "text-embedding-3-small",
        ]
        if china_mode == "owned":
            expected_names *= 2
        assert sorted(
            item["model_name"] for item in groups.json()["candidates"]
        ) == sorted(expected_names)
        update = client.put(
            f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
        )
        assert update.status_code == 200, update.text
        assert sum(len(models) for models in stored().values()) == (
            3 if china_mode == "owned" else 2
        )
    finally:
        run_async(upstream.aclose())


def test_channel_model_sync_deletes_models_that_leave_the_catalog(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "*", "cred-b": "*"}),
    )
    upstream_models = ["gpt-4o", "gpt-4o-mini"]

    async def fake_fetch(_channel: Any) -> list[str]:
        return list(upstream_models)

    _patch_upstream_models(monkeypatch, fake_fetch)
    _run_model_sync(client, admin_headers)

    upstream_models.remove("gpt-4o-mini")
    result = _run_model_sync(client, admin_headers)

    assert {
        (item["credential_id"], tuple(item["missing"])) for item in result["items"]
    } == {("cred-a", ("gpt-4o-mini",)), ("cred-b", ("gpt-4o-mini",))}
    assert _stored_models(client, admin_headers) == {
        ("cred-a", "gpt-4o"),
        ("cred-b", "gpt-4o"),
    }


def test_channel_model_sync_keeps_admin_settings_on_existing_rows(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(
            patterns={"cred-a": "*", "cred-b": "*"},
            models=[_model("gpt-4o", enabled=False, context_window=64000)],
        ),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o"]

    _patch_upstream_models(monkeypatch, fake_fetch)
    _run_model_sync(client, admin_headers)

    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    model = next(
        item
        for item in site["protocols"][0]["models"]
        if item["model_name"] == "gpt-4o"
    )

    assert model["enabled"] is False
    assert model["context_window"] == 64000


def test_channel_model_sync_applies_each_key_filter_separately(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "^gpt-.*", "cred-b": "^claude-.*"}),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o", "claude-3-opus"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    _run_model_sync(client, admin_headers)

    assert _stored_models(client, admin_headers) == {
        ("cred-a", "gpt-4o"),
        ("cred-b", "claude-3-opus"),
    }


def test_channel_model_sync_can_limit_the_credential_scope(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(
            patterns={"cred-a": "*", "cred-b": "*"},
            models=[
                _model("old-a", credential_id="cred-a"),
                _model("old-b", credential_id="cred-b"),
            ],
        ),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["new-model"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    site_id = site["id"]
    result = _run_model_sync(
        client,
        admin_headers,
        site_ids=[site_id],
        credential_ids=["cred-a"],
    )

    assert [item["credential_id"] for item in result["items"]] == ["cred-a"]
    assert _stored_models(client, admin_headers) == {
        ("cred-a", "new-model"),
        ("cred-b", "old-b"),
    }


def test_site_rejects_an_invalid_model_pattern(client, admin_headers) -> None:
    payload = _sync_site_payload(patterns={"cred-a": "("})

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert response.status_code == 422, response.text
    assert "Invalid model pattern" in response.text


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
    payload = _sync_site_payload(
        patterns={"cred-a": "*", "cred-b": "*"},
        models=[_model("gpt-4o", credential_id="cred-a")],
    )
    _create_sync_site(client, admin_headers, payload)

    async def fake_fetch(channel: Any) -> list[str]:
        if channel.keys[0].id == "cred-b":
            return ["gpt-4o"]
        if isinstance(failed_catalog, Exception):
            raise failed_catalog
        return failed_catalog

    _patch_upstream_models(monkeypatch, fake_fetch)

    result = _run_model_sync(client, admin_headers)

    assert {(item["credential_id"], item["status"]) for item in result["items"]} == {
        ("cred-a", "failed"),
        ("cred-b", "updated"),
    }
    # The failing key keeps the row an earlier sync stored.
    assert _stored_models(client, admin_headers) == {
        ("cred-a", "gpt-4o"),
        ("cred-b", "gpt-4o"),
    }


@pytest.mark.parametrize(
    ("site_fields", "is_site_disabled", "sync_request"),
    [
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


def test_site_rejects_duplicate_models(
    client,
    admin_headers,
) -> None:
    payload = _sync_site_payload(models=[_model("gpt-4o")])
    payload["protocols"][0]["models"].append(_model("gpt-4o"))

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert_error(response, 400, "Duplicate model in protocol config")


def test_model_rule_survives_a_backup_round_trip(client, admin_headers) -> None:
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(patterns={"cred-a": "^gpt-4.*"}),
    )

    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200, exported.text
    bundle = exported.json()

    client.delete("/api/admin/sites", headers=admin_headers)
    imported = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("backup.json", json.dumps(bundle), "application/json")},
    )
    assert imported.status_code == 200, imported.text

    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    patterns = {
        credential["id"]: credential["model_pattern"]
        for credential in site["credentials"]
    }
    assert patterns == {"cred-a": "^gpt-4.*", "cred-b": ""}


def test_sync_removes_group_members_when_a_rule_stops_matching(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    payload = _sync_site_payload(patterns={"cred-a": "^gpt-.*", "cred-b": "^none$"})
    site_id = _create_sync_site(client, admin_headers, payload)

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o"]

    _patch_upstream_models(monkeypatch, fake_fetch)
    _run_model_sync(client, admin_headers)
    assert [
        group["name"]
        for group in client.get("/api/admin/model-groups", headers=admin_headers).json()
    ] == ["gpt-4o"]

    payload["credentials"][0]["model_pattern"] = "^none$"
    saved = client.put(
        f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
    )
    assert saved.status_code == 200, saved.text
    _run_model_sync(client, admin_headers)

    assert _stored_models(client, admin_headers) == set()
    group = client.get("/api/admin/model-groups", headers=admin_headers).json()[0]
    assert (group["name"], group["items"]) == ("gpt-4o", [])
