from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from conftest import (
    gateway_headers,
    json_response,
    run_async,
    valid_site_payload,
)
from fastapi.responses import JSONResponse

from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.protocols import ProtocolKind, RequestLogLifecycleStatus
from app.persistence.entities import GatewayApiKeyEntity


def _protocol_group_item(
    protocol: str,
    model_name: str,
    *,
    protocol_config_id: str = "pc-1",
    credential_id: str = "cred-1",
) -> dict[str, Any]:
    return {
        "channel_id": compose_runtime_channel_id(
            protocol_config_id, ProtocolKind(protocol)
        ),
        "credential_id": credential_id,
        "model_name": model_name,
        "enabled": True,
    }


def _create_failover_group(
    *,
    client: Any,
    admin_headers: dict[str, Any],
    create_site: Any,
    create_model_group: Any,
) -> None:
    """Create two sites with a failover model group for upstream error tests."""
    create_site(
        valid_site_payload(
            name="First",
            base_id="ba",
            credential_id="ca",
            protocol_config_id="pa",
            model_name="m-a",
        )
    )
    create_site(
        valid_site_payload(
            name="Second",
            base_id="bb",
            credential_id="cb",
            protocol_config_id="pb",
            model_name="m-b",
        )
    )
    group = create_model_group(
        name="fail-group",
        items=[
            _protocol_group_item(
                "openai_chat",
                "m-a",
                protocol_config_id="pa",
                credential_id="ca",
            ),
            _protocol_group_item(
                "openai_chat",
                "m-b",
                protocol_config_id="pb",
                credential_id="cb",
            ),
        ],
    )
    update = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"strategy": "failover"},
    )
    assert update.status_code == 200, update.text


async def _set_gateway_spend(app_state: Any, key_id: str, spent: float) -> None:
    async with app_state.session_factory() as session:
        entity = await session.get(GatewayApiKeyEntity, key_id)
        assert entity is not None
        entity.spent_cost_usd = spent
        await session.commit()


@pytest.mark.parametrize(
    ("path", "body", "expected"),
    [
        (
            "/v1/chat/completions",
            {"model": "gpt-4o"},
            {
                "error": {
                    "message": "Missing gateway API key",
                    "type": "unauthorized",
                    "param": None,
                    "code": None,
                }
            },
        ),
        (
            "/v1/messages",
            {"model": "claude-3"},
            {
                "type": "error",
                "error": {
                    "type": "authentication_error",
                    "message": "Missing gateway API key",
                },
            },
        ),
        (
            "/v1beta/models/gemini-2.5-flash:generateContent",
            {"contents": []},
            {
                "error": {
                    "code": 401,
                    "message": "Missing gateway API key",
                    "status": "UNAUTHENTICATED",
                }
            },
        ),
    ],
)
def test_proxy_uses_protocol_error_format_for_missing_gateway_key(
    client,
    path: str,
    body: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    response = client.post(path, json=body)

    assert response.status_code == 401
    assert response.json() == expected


def test_gateway_key_auth_accepts_x_api_key_header(
    client,
    create_site_group_and_key,
) -> None:
    _site, _group, key = create_site_group_and_key()

    response = client.get("/v1/models", headers={"x-api-key": key["api_key"]})

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "gpt-4o"


def test_gateway_key_auth_accepts_x_goog_api_key_header(
    client,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    create_site(valid_site_payload(protocols=["gemini"], model_name="gemini-pro"))
    create_model_group(
        name="gemini-pro",
        items=[_protocol_group_item("gemini", "gemini-pro")],
    )
    key = create_gateway_key()

    response = client.get("/v1beta/models", headers={"x-goog-api-key": key["api_key"]})

    assert response.status_code == 200
    assert response.json()["models"][0]["name"] == "models/gemini-pro"


def test_gateway_key_auth_rejects_invalid_disabled_expired_and_spent_keys(
    client,
    app_state,
    create_gateway_key,
) -> None:
    invalid = client.get("/v1/models", headers={"x-api-key": "missing"})
    disabled_key = create_gateway_key(enabled=False)
    disabled = client.get("/v1/models", headers=gateway_headers(disabled_key))
    expired_key = create_gateway_key(expires_at="2000-01-01T00:00:00Z")
    expired = client.get("/v1/models", headers=gateway_headers(expired_key))
    spent_key = create_gateway_key(max_cost_usd=1)
    run_async(_set_gateway_spend(app_state, spent_key["id"], 1))
    spent = client.get("/v1/models", headers=gateway_headers(spent_key))

    assert invalid.status_code == 401
    assert invalid.json()["error"]["message"] == "Invalid gateway API key"
    assert disabled.json()["error"]["message"] == "Gateway API key is disabled"
    assert expired.json()["error"]["message"] == "Gateway API key has expired"
    assert spent.json()["error"]["message"] == (
        "Gateway API key has reached the max balance"
    )


def test_proxy_json_endpoints_forward_expected_protocol_and_body(
    client,
    monkeypatch,
    create_gateway_key,
) -> None:
    key = create_gateway_key()
    calls: list[dict[str, Any]] = []

    async def fake_proxy(
        protocol: ProtocolKind,
        body: dict[str, Any],
        gateway_key: Any,
        user_agent: str | None,
        forwarded_headers: dict[str, str] | None = None,
        *,
        path_suffix: str = "",
        multipart_files: list[Any] | None = None,
    ) -> JSONResponse:
        calls.append(
            {
                "protocol": protocol.value,
                "body": body,
                "gateway_key_id": gateway_key.id,
                "user_agent": user_agent,
                "forwarded_headers": forwarded_headers or {},
                "path_suffix": path_suffix,
                "multipart_files": multipart_files or [],
            }
        )
        return json_response({"ok": True, "protocol": protocol.value})

    import app.gateway.service.proxy_routes as proxy_routes

    monkeypatch.setattr(proxy_routes, "_proxy_protocol", fake_proxy)
    headers = {**gateway_headers(key), "User-Agent": "lens-tests"}

    cases = [
        (
            "post",
            "/v1/chat/completions",
            {"model": "gpt-4o", "stream": True},
            "openai_chat",
            {"model": "gpt-4o", "stream": True},
        ),
        (
            "post",
            "/v1/responses",
            {"model": "gpt-4o", "input": "hello"},
            "openai_responses",
            {"model": "gpt-4o", "input": "hello"},
        ),
        (
            "post",
            "/v1/embeddings",
            {"model": "text-embedding-3-small", "stream": True},
            "openai_embedding",
            {"model": "text-embedding-3-small"},
        ),
        (
            "post",
            "/v1/rerank",
            {"model": "reranker", "stream": True},
            "rerank",
            {"model": "reranker"},
        ),
        (
            "post",
            "/v1/images/generations",
            {"model": "gpt-image-1", "prompt": "test"},
            "openai_image",
            {"model": "gpt-image-1", "prompt": "test"},
        ),
        (
            "post",
            "/v1/messages",
            {"model": "claude-3", "messages": []},
            "anthropic",
            {"model": "claude-3", "messages": []},
        ),
        (
            "post",
            "/v1beta/models/gemini-2.5-flash:generateContent",
            {"contents": []},
            "gemini",
            {"contents": [], "model": "gemini-2.5-flash", "stream": False},
        ),
        (
            "post",
            "/v1beta/models/gemini-2.5-flash:streamGenerateContent",
            {"contents": []},
            "gemini",
            {"contents": [], "model": "gemini-2.5-flash", "stream": True},
        ),
    ]

    for _method, path, body, expected_protocol, expected_body in cases:
        response = client.post(path, headers=headers, json=body)
        assert response.status_code == 200, response.text
        assert response.json()["protocol"] == expected_protocol
        assert calls[-1]["body"] == expected_body
        assert calls[-1]["gateway_key_id"] == key["id"]
        assert calls[-1]["user_agent"] == "lens-tests"

    image_call = next(item for item in calls if item["protocol"] == "openai_image")
    assert image_call["path_suffix"] == "images/generations"


def test_responses_proxy_preserves_input_shape(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    captured_bodies: list[dict[str, Any]] = []

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        captured_bodies.append(json.loads(body_bytes))
        return httpx.Response(
            200,
            json={
                "id": "resp_1",
                "object": "response",
                "model": "gpt-5.6-sol",
                "output": [],
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "total_tokens": 2,
                },
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_RESPONSES.value],
            model_name="gpt-5.6-sol",
        )
    )
    create_model_group(
        name="response-model",
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_RESPONSES
                ),
                "credential_id": "cred-1",
                "model_name": "gpt-5.6-sol",
                "enabled": True,
            }
        ],
    )
    key = create_gateway_key()
    input_items = [
        {"role": "user", "content": "Use the lookup tool."},
        {
            "type": "function_call",
            "call_id": "call_1",
            "name": "lookup",
            "arguments": '{"query":"lens"}',
        },
        {"role": "assistant", "content": ""},
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": "result",
        },
    ]
    request_bodies = [
        {"model": "response-model", "input": "  Keep surrounding whitespace.  "},
        {"model": "response-model", "input": input_items},
    ]

    for body in request_bodies:
        response = client.post(
            "/v1/responses",
            headers=gateway_headers(key),
            json=body,
        )
        assert response.status_code == 200, response.text

    assert captured_bodies == [
        {"model": "gpt-5.6-sol", "input": body["input"]} for body in request_bodies
    ]


def test_model_group_param_override_has_highest_priority(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    captured_body: dict[str, Any] = {}
    captured_headers: dict[str, str] = {}

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        captured_body.update(json.loads(body_bytes))
        captured_headers.update(upstream.headers)
        return httpx.Response(
            500,
            json={"error": {"message": "stop after capture"}},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    settings = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {
                    "key": "upstream_param_override_config",
                    "value": json.dumps(
                        {
                            "rules": [
                                {"path": "temperature", "action": "set", "value": 0.8},
                                {
                                    "path": "metadata.global",
                                    "action": "set",
                                    "value": True,
                                },
                                {
                                    "path": "metadata.priority",
                                    "action": "set",
                                    "value": "global",
                                },
                            ]
                        }
                    ),
                },
                {
                    "key": "upstream_headers_config",
                    "value": json.dumps(
                        {
                            "rules": [
                                {
                                    "name": "X-Priority",
                                    "action": "override",
                                    "value": "global",
                                },
                                {
                                    "name": "X-Global",
                                    "action": "override",
                                    "value": "yes",
                                },
                            ]
                        }
                    ),
                },
            ]
        },
    )
    assert settings.status_code == 200, settings.text
    site_payload = valid_site_payload(model_name="gpt-4o")
    site_payload["protocols"][0]["param_override"] = [
        {"path": "temperature", "action": "set", "value": 0.5},
        {"path": "metadata.channel", "action": "set", "value": True},
        {"path": "metadata.priority", "action": "set", "value": "channel"},
    ]
    site_payload["protocols"][0]["headers"] = [
        {"name": "X-Priority", "action": "override", "value": "channel"},
        {"name": "X-Channel", "action": "override", "value": "yes"},
    ]
    create_site(site_payload)
    group_response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "client-model",
            "param_override": [
                {"path": "temperature", "action": "set", "value": 0.2},
                {"path": "metadata.group", "action": "set", "value": True},
                {"path": "metadata.priority", "action": "set", "value": "group"},
            ],
            "headers": [
                {"name": "X-Priority", "action": "override", "value": "group"},
                {"name": "X-Group", "action": "override", "value": "yes"},
            ],
            "items": [_protocol_group_item("openai_chat", "gpt-4o")],
        },
    )
    assert group_response.status_code == 201, group_response.text
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "client-model",
            "messages": [],
            "temperature": 1.0,
            "metadata": {"request": True, "priority": "request"},
        },
    )

    assert response.status_code == 502, response.text
    assert captured_body["model"] == "gpt-4o"
    assert captured_body["temperature"] == 0.2
    assert captured_body["metadata"] == {
        "request": True,
        "global": True,
        "channel": True,
        "group": True,
        "priority": "group",
    }
    headers = {key.lower(): value for key, value in captured_headers.items()}
    assert headers["x-priority"] == "group"
    assert headers["x-global"] == "yes"
    assert headers["x-channel"] == "yes"
    assert headers["x-group"] == "yes"


def test_image_proxy_logs_non_token_billing(
    client,
    admin_headers,
    app_state,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream
    import app.gateway.service.streaming.stream_logging as stream_logging

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        assert json.loads(body_bytes)["model"] == "gpt-image-1"
        return httpx.Response(
            200,
            json={"data": [{"b64_json": "first"}, {"b64_json": "second"}]},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    monkeypatch.setattr(stream_logging, "app_state", app_state)
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_IMAGE.value],
            model_name="gpt-image-1",
        )
    )
    create_model_group(
        name="gpt-image-1",
        items=[_protocol_group_item("openai_image", "gpt-image-1")],
    )
    channels = run_async(app_state.channel_store.list_channels())
    channel = channels[0].model_copy(
        update={
            "keys": [channels[0].keys[0].model_copy(update={"rate_multiplier": 2.0})]
        }
    )

    async def list_channels_with_rate() -> list[Any]:
        return [channel]

    monkeypatch.setattr(
        app_state.channel_store, "list_channels", list_channels_with_rate
    )
    price_response = client.put(
        "/api/admin/model-prices/gpt-image-1",
        headers=admin_headers,
        json={
            "model_key": "gpt-image-1",
            "pricing_mode": "non_tokens",
            "image_price_per_image": 0.04,
        },
    )
    assert price_response.status_code == 200, price_response.text
    key = create_gateway_key()

    response = client.post(
        "/v1/images/generations",
        headers=gateway_headers(key),
        json={"model": "gpt-image-1", "prompt": "test", "n": 3},
    )

    assert response.status_code == 200, response.text
    logs = client.get("/api/admin/request-logs/page", headers=admin_headers)

    assert logs.status_code == 200, logs.text
    log = logs.json()["items"][0]
    assert log["rate_multiplier"] == 2.0
    assert log["billing_mode"] == "non_tokens"
    assert log["billing_units"] == 2
    assert log["output_cost_usd"] == 0.16
    assert log["total_cost_usd"] == 0.16


@pytest.mark.parametrize(
    "upstream_protocol",
    [
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.ANTHROPIC,
        ProtocolKind.OPENAI_RESPONSES,
    ],
)
def test_anthropic_proxy_promotes_system_messages(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    upstream_protocol: ProtocolKind,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    captured_body: dict[str, Any] = {}

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        captured_body.update(json.loads(body_bytes))
        return httpx.Response(
            500,
            json={"error": {"message": "stop after capture"}},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    create_site(
        valid_site_payload(
            protocols=[upstream_protocol.value],
            model_name="upstream-model",
        )
    )
    create_model_group(
        name="client-model",
        items=[_protocol_group_item(upstream_protocol.value, "upstream-model")],
    )
    key = create_gateway_key()

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(key),
        json={
            "model": "client-model",
            "max_tokens": 16,
            "system": "Initial instruction.",
            "messages": [
                {"role": "user", "content": "First question."},
                {"role": "system", "content": "Updated instruction."},
                {"role": "user", "content": "Second question."},
            ],
        },
    )

    assert response.status_code == 502, response.text
    user_messages = [
        {"role": "user", "content": "First question."},
        {"role": "user", "content": "Second question."},
    ]
    if upstream_protocol == ProtocolKind.ANTHROPIC:
        assert captured_body["system"] == [
            {"type": "text", "text": "Initial instruction."},
            {"type": "text", "text": "Updated instruction."},
        ]
        assert captured_body["messages"] == user_messages
    else:
        payload_key = (
            "messages" if upstream_protocol == ProtocolKind.OPENAI_CHAT else "input"
        )
        assert captured_body[payload_key] == [
            {
                "role": "system",
                "content": "Initial instruction.\nUpdated instruction.",
            },
            *user_messages,
        ]


def test_failover_orders_targets_and_tracks_active_credential(
    client,
    admin_headers,
    app_state,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    first_site = valid_site_payload(
        name="First site",
        base_id="base-a",
        credential_id="cred-a",
        protocol_config_id="pc-a",
        model_name="model-a1",
    )
    first_site["protocols"][0]["models"].append(
        {
            "credential_id": "cred-a",
            "model_name": "model-a2",
            "enabled": True,
            "protocol": ProtocolKind.OPENAI_CHAT.value,
        }
    )
    first_site["credentials"][0]["name"] = "l3"
    create_site(first_site)
    second_site = valid_site_payload(
        name="Second site",
        base_id="base-b",
        credential_id="cred-b",
        protocol_config_id="pc-b",
        model_name="model-b",
    )
    second_site["credentials"][0]["name"] = "feng-key"
    second_site["credentials"].append(
        {
            "id": "cred-b-alt",
            "name": "feng-backup",
            "api_key": "upstream-secret-alt",
            "enabled": True,
        }
    )
    second_site["protocols"][0]["credential_ids"].append("cred-b-alt")
    second_site["protocols"][0]["models"].append(
        {
            "credential_id": "cred-b-alt",
            "model_name": "model-b-alt",
            "enabled": True,
            "protocol": ProtocolKind.OPENAI_CHAT.value,
        }
    )
    create_site(second_site)
    group = create_model_group(
        name="failover-group",
        items=[
            _protocol_group_item(
                "openai_chat",
                "model-a1",
                protocol_config_id="pc-a",
                credential_id="cred-a",
            ),
            _protocol_group_item(
                "openai_chat",
                "model-b",
                protocol_config_id="pc-b",
                credential_id="cred-b",
            ),
            _protocol_group_item(
                "openai_chat",
                "model-a2",
                protocol_config_id="pc-a",
                credential_id="cred-a",
            ),
        ],
    )
    update = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"strategy": "failover"},
    )
    assert update.status_code == 200, update.text

    attempted_models: list[str] = []

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        model_name = str(json.loads(body_bytes)["model"])
        attempted_models.append(model_name)
        request = httpx.Request("POST", upstream.url)
        if model_name != "model-b":
            return httpx.Response(
                500,
                json={"error": {"message": "failed"}},
                request=request,
            )
        page = await app_state.request_log_store.list_request_log_page()
        active_log = page.items[0]
        assert active_log.lifecycle_status == RequestLogLifecycleStatus.CONNECTING
        assert active_log.channel_name == "Second site"
        assert active_log.credential_id == "cred-b"
        assert active_log.credential_name == "feng-key"
        assert active_log.channel_has_multiple_credentials is True
        assert active_log.attempt_count == 3
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 0,
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
            request=request,
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "failover-group", "messages": []},
    )
    assert response.status_code == 200, response.text

    page_response = client.get("/api/admin/request-logs/page", headers=admin_headers)
    assert page_response.status_code == 200, page_response.text
    detail_response = client.get(
        f"/api/admin/request-logs/{page_response.json()['items'][0]['id']}",
        headers=admin_headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()

    assert attempted_models == ["model-a1", "model-a2", "model-b"]
    assert [attempt["channel_name"] for attempt in detail["attempts"]] == [
        "First site",
        "First site",
        "Second site",
    ]
    assert [attempt["success"] for attempt in detail["attempts"]] == [
        False,
        False,
        True,
    ]


def test_upstream_400_passes_through_body_without_failover(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    _create_failover_group(
        client=client,
        admin_headers=admin_headers,
        create_site=create_site,
        create_model_group=create_model_group,
    )

    attempted: list[str] = []

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        attempted.append(json.loads(body_bytes)["model"])
        return httpx.Response(
            400,
            content="Error: [provider.api_error] 400 缺少 text 字段".encode(),
            headers={"content-type": "text/plain; charset=utf-8"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "fail-group", "messages": []},
    )

    assert response.status_code == 400, response.text
    assert "缺少 text 字段" in response.json()["error"]["message"]
    assert attempted == ["m-a"]


def test_upstream_400_stream_passes_through_body(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    create_site(valid_site_payload(model_name="bad-model"))
    create_model_group(
        name="bad-model",
        items=[_protocol_group_item("openai_chat", "bad-model")],
    )

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert stream
        return httpx.Response(
            400,
            content="Error: [provider.api_error] 400 缺少 text 字段".encode(),
            headers={"content-type": "text/plain; charset=utf-8"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "bad-model", "messages": [], "stream": True},
    )

    assert response.status_code == 400, response.text
    assert "缺少 text 字段" in response.json()["error"]["message"]


def test_all_upstream_fail_returns_first_specific_message(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    _create_failover_group(
        client=client,
        admin_headers=admin_headers,
        create_site=create_site,
        create_model_group=create_model_group,
    )

    attempted: list[str] = []

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        model = json.loads(body_bytes)["model"]
        attempted.append(model)
        request = httpx.Request("POST", upstream.url)
        content = (
            b'{"error":{"message":"upstream-a exploded"}}'
            if model == "m-a"
            else b'{"error":{"message":"upstream-b exploded"}}'
        )
        return httpx.Response(
            500,
            content=content,
            headers={"content-type": "application/json"},
            request=request,
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "fail-group", "messages": []},
    )

    assert response.status_code == 502, response.text
    assert "upstream-a exploded" in response.json()["error"]["message"]
    assert attempted == ["m-a", "m-b"]


def test_all_channels_in_cooldown_logs_the_cooled_channel_names(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    _create_failover_group(
        client=client,
        admin_headers=admin_headers,
        create_site=create_site,
        create_model_group=create_model_group,
    )

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"message": "rate limited"}},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()
    first = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "fail-group", "messages": []},
    )
    assert first.status_code == 502, first.text

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "fail-group", "messages": []},
    )

    assert response.status_code == 503, response.text
    page = client.get("/api/admin/request-logs/page", headers=admin_headers)
    assert page.status_code == 200, page.text
    error_message = page.json()["items"][0]["error_message"]
    assert "First/m-a (rate_limit," in error_message
    assert "Second/m-b (rate_limit," in error_message


def _anthropic_group(
    create_site: Any, create_model_group: Any, *, name: str = "claude-group"
) -> None:
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.ANTHROPIC.value],
            model_name="claude-upstream",
        )
    )
    create_model_group(
        name=name,
        items=[_protocol_group_item("anthropic", "claude-upstream")],
    )


def test_anthropic_non_stream_accepts_sse_body_labelled_as_json(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    _anthropic_group(create_site, create_model_group)

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        events = [
            {
                "type": "message_start",
                "message": {
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-upstream",
                    "content": [],
                    "usage": {"input_tokens": 5, "output_tokens": 0},
                },
            },
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "hi"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 2},
            },
            {"type": "message_stop"},
        ]
        body = "".join(f"data: {json.dumps(event)}\n\n" for event in events)
        return httpx.Response(
            200,
            content=body.encode("utf-8"),
            # Upstream answers with SSE but mislabels the content-type.
            headers={"content-type": "application/json"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(key),
        json={"model": "claude-group", "messages": [], "max_tokens": 16},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == "msg_1"
    assert payload["content"] == [{"type": "text", "text": "hi"}]
    assert payload["stop_reason"] == "end_turn"


def test_non_json_upstream_body_reports_the_body_not_usage(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    _anthropic_group(create_site, create_model_group)

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        return httpx.Response(
            200,
            content=b"",
            headers={"content-type": "application/json"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(key),
        json={"model": "claude-group", "messages": [], "max_tokens": 16},
    )

    assert response.status_code == 502, response.text
    message = response.json()["error"]["message"]
    assert "Invalid upstream response body" in message
    assert "0 bytes" in message
    assert "Invalid upstream usage" not in message


@pytest.mark.parametrize(
    ("protocol", "path", "body"),
    [
        (
            ProtocolKind.ANTHROPIC,
            "/v1/messages",
            {"model": "client-model", "messages": [], "max_tokens": 16},
        ),
        (
            ProtocolKind.RERANK,
            "/v1/rerank",
            {"model": "client-model", "query": "ping", "documents": ["pong"]},
        ),
    ],
)
def test_html_upstream_body_is_summarised_by_title(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    protocol: ProtocolKind,
    path: str,
    body: dict[str, Any],
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    create_site(
        valid_site_payload(protocols=[protocol.value], model_name="upstream-model")
    )
    create_model_group(
        name="client-model",
        items=[_protocol_group_item(protocol.value, "upstream-model")],
    )

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        return httpx.Response(
            200,
            content=b"<html><head><title>502 Bad Gateway</title></head></html>",
            headers={"content-type": "text/html"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()

    response = client.post(
        path,
        headers=gateway_headers(key),
        json=body,
    )

    assert response.status_code == 502, response.text
    message = response.json()["error"]["message"]
    assert "Invalid upstream response body" in message
    assert "502 Bad Gateway" in message
    assert "<html>" not in message
