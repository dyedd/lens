from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
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
    include_rules: list[str] | None = None,
    exclude_rules: list[str] | None = None,
    models: list[dict[str, Any]] | None = None,
    **site_fields: Any,
) -> dict[str, Any]:
    """Build a two-credential site with onboarding rules and stored models."""
    return {
        "name": "Multi-key Site",
        **site_fields,
        "model_sync_include_rule_ids": include_rules or [],
        "model_sync_exclude_rule_ids": exclude_rules or [],
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
                "models": (models if models is not None else [_model("manual-only")]),
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


def _stored_models(client, admin_headers) -> set[tuple[str, str, bool]]:
    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    return {
        (
            model["credential_id"],
            model["model_name"],
            model["upstream_missing"],
        )
        for model in site["protocols"][0]["models"]
    }


def test_channel_model_sync_onboards_models_matching_include_rules(
    client,
    admin_headers,
    create_regex_rule,
    monkeypatch,
) -> None:
    rule = create_regex_rule("GPT", "^(gpt-4o|O1-mini)$")
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(include_rules=[rule["id"]]),
    )

    async def fake_fetch(channel: Any) -> list[str]:
        assert len(channel.keys) == 1
        return ["gpt-4o", "GPT-4o-preview", "O1-mini", "claude-3-opus"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    result = _run_model_sync(client, admin_headers)

    assert {
        (item["credential_id"], item["status"], tuple(sorted(item["added"])))
        for item in result["items"]
    } == {
        ("cred-a", "updated", ("O1-mini", "gpt-4o")),
        ("cred-b", "updated", ("O1-mini", "gpt-4o")),
    }
    assert _stored_models(client, admin_headers) == {
        ("cred-a", "manual-only", True),
        ("cred-a", "gpt-4o", False),
        ("cred-a", "O1-mini", False),
        ("cred-b", "gpt-4o", False),
        ("cred-b", "O1-mini", False),
    }


def test_channel_model_sync_auto_creates_group_for_new_models(
    client,
    admin_headers,
    create_regex_rule,
    monkeypatch,
) -> None:
    rule = create_regex_rule("GPT", "^gpt-4o$")
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(include_rules=[rule["id"]], models=[]),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o"]

    _patch_upstream_models(monkeypatch, fake_fetch)

    result = _run_model_sync(client, admin_headers)
    groups = client.get("/api/admin/model-groups", headers=admin_headers).json()

    assert [group["name"] for group in result["groups"]["created_groups"]] == ["gpt-4o"]
    assert result["groups"]["pending"] == []
    assert [
        (
            group["name"],
            group["origin"],
            group["strategy"],
            tuple(sorted(item["credential_id"] for item in group["items"])),
            {item["source"] for item in group["items"]},
        )
        for group in groups
    ] == [("gpt-4o", "auto", "failover", ("cred-a", "cred-b"), {"placement"})]

    second = _run_model_sync(client, admin_headers)
    assert second["groups"]["pending"] == []
    assert len(client.get("/api/admin/model-groups", headers=admin_headers).json()) == 1


def test_channel_model_sync_removes_empty_auto_group(
    client,
    admin_headers,
    create_regex_rule,
    monkeypatch,
) -> None:
    rule = create_regex_rule("GPT", "^gpt-4o$")
    payload = _sync_site_payload(include_rules=[rule["id"]], models=[])
    site_id = _create_sync_site(client, admin_headers, payload)

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o"]

    _patch_upstream_models(monkeypatch, fake_fetch)
    _run_model_sync(client, admin_headers)
    assert len(client.get("/api/admin/model-groups", headers=admin_headers).json()) == 1

    payload["model_sync_include_rule_ids"] = []
    payload["protocols"][0]["models"] = []
    saved = client.put(
        f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
    )

    assert saved.status_code == 200, saved.text
    assert client.get("/api/admin/model-groups", headers=admin_headers).json() == []


@pytest.mark.parametrize("exclude", [True, False])
def test_removing_unplaced_model_can_exclude_it_from_onboarding(
    client,
    admin_headers,
    create_regex_rule,
    monkeypatch,
    exclude: bool,
) -> None:
    # The near name keeps the model out of automatic groups, so it stays
    # unplaced and can be removed from the待分配 panel.
    client.post(
        "/api/admin/model-groups", headers=admin_headers, json={"name": "gpt-4.o"}
    )
    rule = create_regex_rule("GPT", "^gpt-4o$")
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(include_rules=[rule["id"]]),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o"]

    _patch_upstream_models(monkeypatch, fake_fetch)
    _run_model_sync(client, admin_headers)

    removed = client.post(
        "/api/admin/unplaced-model-removals",
        headers=admin_headers,
        json={"model_names": ["gpt-4o"], "exclude": exclude},
    )
    assert removed.status_code == 200, removed.text
    assert removed.json() == {
        "deleted": 2,
        "excluded": 1 if exclude else 0,
    }

    _run_model_sync(client, admin_headers)
    site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    names = {model["model_name"] for model in site["protocols"][0]["models"]}
    if exclude:
        assert "gpt-4o" not in names
        rules = {
            rule["id"]: rule["pattern"]
            for rule in client.get(
                "/api/admin/regex-rules", headers=admin_headers
            ).json()
        }
        assert [rules[rule_id] for rule_id in site["model_sync_exclude_rule_ids"]] == [
            "^gpt-4o$"
        ]
    else:
        assert "gpt-4o" in names


def test_channel_model_sync_flags_vanished_models_instead_of_deleting_them(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    payload = _sync_site_payload(models=[_model("manual-only"), _model("gpt-old")])
    _create_sync_site(client, admin_headers, payload)
    upstream_models = ["gpt-new", "manual-only"]

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
    assert ("cred-a", "gpt-old", True) in flagged_models
    assert ("cred-a", "manual-only", False) in flagged_models
    assert all(model[1] != "gpt-new" for model in flagged_models)
    assert {
        (item["credential_id"], tuple(item["restored"])) for item in restored["items"]
    } == {("cred-a", ("gpt-old",)), ("cred-b", ())}
    assert ("cred-a", "gpt-old", False) in _stored_models(client, admin_headers)


def test_channel_model_sync_retires_members_missing_past_the_grace_period(
    client,
    admin_headers,
    create_regex_rule,
    monkeypatch,
) -> None:
    import app.persistence.channel_store.write as site_write
    import app.persistence.repositories.group_reconcile as group_reconcile

    rule = create_regex_rule("GPT", "^gpt-")
    payload = _sync_site_payload(
        include_rules=[rule["id"]],
        models=[_model("manual-only")],
    )
    _create_group = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "gpt-old"},
    )
    assert _create_group.status_code == 201, _create_group.text
    _create_group = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "gpt-new"},
    )
    assert _create_group.status_code == 201, _create_group.text
    site_id = _create_sync_site(client, admin_headers, payload)

    upstream_models = ["gpt-new", "gpt-old", "manual-only"]

    async def fake_fetch(_channel: Any) -> list[str]:
        return list(upstream_models)

    _patch_upstream_models(monkeypatch, fake_fetch)

    flagged = _run_model_sync(client, admin_headers)
    upstream_models[:] = ["gpt-new", "manual-only"]
    # A site save later in the grace period rebuilds the model rows; the miss
    # must still count from the sync that first saw it.
    first_miss = datetime.now(UTC).replace(tzinfo=None)
    first_missing = _run_model_sync(client, admin_headers)
    monkeypatch.setattr(
        site_write, "_naive_utc_now", lambda: first_miss + timedelta(days=3)
    )
    payload["protocols"][0]["models"] = [
        _model("manual-only"),
        _model("gpt-old", protocol="openai_chat", upstream_missing=True),
        _model(
            "gpt-old",
            credential_id="cred-b",
            protocol="openai_chat",
            upstream_missing=True,
        ),
        _model("gpt-new", protocol="openai_chat"),
        _model("gpt-new", credential_id="cred-b", protocol="openai_chat"),
    ]
    saved = client.put(
        f"/api/admin/sites/{site_id}", headers=admin_headers, json=payload
    )
    upstream_models[:] = ["gpt-new", "manual-only", "gpt-extra"]
    within_grace = _run_model_sync(client, admin_headers)
    monkeypatch.setattr(
        group_reconcile, "_naive_utc_now", lambda: first_miss + timedelta(days=8)
    )
    past_grace = _run_model_sync(client, admin_headers)
    history = client.get("/api/admin/model-sync-runs?limit=100", headers=admin_headers)
    groups = client.get("/api/admin/model-groups", headers=admin_headers).json()

    def changed(run: dict[str, Any], stage: str) -> list[tuple[str, str, str]]:
        return [
            (change["group_name"], change["credential_id"], change["model_name"])
            for change in run["groups"][stage]
        ]

    assert saved.status_code == 200, saved.text
    assert set(changed(flagged, "added")) == {
        ("gpt-new", "cred-a", "gpt-new"),
        ("gpt-new", "cred-b", "gpt-new"),
        ("gpt-old", "cred-a", "gpt-old"),
        ("gpt-old", "cred-b", "gpt-old"),
    }
    assert flagged["groups"]["created_groups"] == []
    assert changed(flagged, "retired") == []
    assert changed(first_missing, "retired") == []
    assert changed(within_grace, "retired") == []
    assert changed(past_grace, "retired") == [
        ("gpt-old", "cred-a", "gpt-old"),
        ("gpt-old", "cred-b", "gpt-old"),
    ]
    assert next(group for group in groups if group["name"] == "gpt-old")["items"] == []
    assert history.status_code == 200, history.text
    assert {run["id"] for run in history.json()} == {
        flagged["id"],
        first_missing["id"],
        within_grace["id"],
        past_grace["id"],
    }


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
        models=[
            _model("manual-only"),
            _model("gpt-old"),
            _model("gpt-new", credential_id="cred-b"),
        ]
    )
    _create_sync_site(client, admin_headers, payload)

    async def fake_fetch(channel: Any) -> list[str]:
        if channel.keys[0].id != "cred-a":
            return ["gpt-new"]
        if isinstance(failed_catalog, Exception):
            raise failed_catalog
        return failed_catalog

    _patch_upstream_models(monkeypatch, fake_fetch)

    result = _run_model_sync(client, admin_headers)

    expected_a_status = "failed" if isinstance(failed_catalog, Exception) else "updated"
    assert {(item["credential_id"], item["status"]) for item in result["items"]} == {
        ("cred-a", expected_a_status),
        ("cred-b", "unchanged"),
    }
    if isinstance(failed_catalog, Exception):
        expected_cred_a = {
            ("cred-a", "manual-only", False),
            ("cred-a", "gpt-old", False),
        }
    else:
        expected_cred_a = {
            ("cred-a", "manual-only", True),
            ("cred-a", "gpt-old", True),
        }
    assert {
        model for model in _stored_models(client, admin_headers) if model[0] == "cred-a"
    } == expected_cred_a


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


def test_site_save_preserves_upstream_missing_flag_for_all_models(
    client,
    admin_headers,
) -> None:
    payload = _sync_site_payload()
    payload["protocols"][0]["models"] = [
        _model("gpt-gone", upstream_missing=True),
        _model("kept-by-admin", upstream_missing=True),
    ]

    _create_sync_site(client, admin_headers, payload)

    assert _stored_models(client, admin_headers) == {
        ("cred-a", "gpt-gone", True),
        ("cred-a", "kept-by-admin", True),
    }


def test_site_rejects_duplicate_models(
    client,
    admin_headers,
) -> None:
    payload = _sync_site_payload()
    payload["protocols"][0]["models"].append(_model("manual-only"))

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert_error(response, 400, "Duplicate model in protocol config")


def test_channel_model_sync_onboards_only_rule_matched_models(
    client,
    admin_headers,
    create_regex_rule,
    monkeypatch,
) -> None:
    rule = create_regex_rule("New", "^new-model$")
    payload = _sync_site_payload(include_rules=[rule["id"]])
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
        ("cred-a", "manual-only"): {"openai_chat"},
        ("cred-a", "new-model"): {"openai_chat"},
        ("cred-b", "new-model"): {"openai_chat"},
    }


def test_channel_model_sync_exclude_rules_veto_include_matches(
    client,
    admin_headers,
    create_regex_rule,
    monkeypatch,
) -> None:
    include = create_regex_rule("Family", "^gpt-")
    exclude = create_regex_rule("Legacy", "preview$")
    _create_sync_site(
        client,
        admin_headers,
        _sync_site_payload(
            include_rules=[include["id"]],
            exclude_rules=[exclude["id"]],
        ),
    )

    async def fake_fetch(_channel: Any) -> list[str]:
        return ["gpt-4o", "gpt-4o-preview"]

    _patch_upstream_models(monkeypatch, fake_fetch)
    _run_model_sync(client, admin_headers)

    assert _stored_models(client, admin_headers) == {
        ("cred-a", "manual-only", True),
        ("cred-a", "gpt-4o", False),
        ("cred-b", "gpt-4o", False),
    }
