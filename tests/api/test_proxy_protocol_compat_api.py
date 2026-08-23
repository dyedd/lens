from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from conftest import gateway_headers, run_async, valid_site_payload

from lens_api.core.runtime_channel_ids import compose_runtime_channel_id
from lens_api.models import ProtocolKind
from lens_api.persistence.shared import SETTING_RELAY_LOG_BODY_ENABLED, SettingItem


def _chat_group_item(model_name: str) -> dict[str, Any]:
    return {
        "channel_id": compose_runtime_channel_id("pc-1", ProtocolKind.OPENAI_CHAT),
        "credential_id": "cred-1",
        "model_name": model_name,
        "enabled": True,
    }


def test_same_protocol_responses_request_preserves_body_shape(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    from lens_api.gateway.service import proxy_upstream

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
            protocols=[ProtocolKind.OPENAI_RESPONSES.value],
            model_name="responses-upstream",
        )
    )
    create_model_group(
        name="responses-client",
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_RESPONSES
                ),
                "credential_id": "cred-1",
                "model_name": "responses-upstream",
                "enabled": True,
            }
        ],
    )
    body = {
        "model": "responses-client",
        "input": "  preserve this input exactly  ",
        "tools": [{"type": "function", "name": "lookup", "parameters": {}}],
        "tool_choice": "auto",
    }

    response = client.post(
        "/v1/responses",
        headers=gateway_headers(create_gateway_key()),
        json=body,
    )

    assert response.status_code == 502, response.text
    assert captured_body == {**body, "model": "responses-upstream"}


@pytest.mark.parametrize(
    ("client_protocol", "route"),
    [
        (ProtocolKind.ANTHROPIC, "/v1/messages"),
        (ProtocolKind.OPENAI_CHAT, "/v1/chat/completions"),
    ],
)
def test_glm_chat_requests_normalize_reasoning_controls(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    client_protocol: ProtocolKind,
    route: str,
) -> None:
    from lens_api.gateway.service import proxy_upstream

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
            protocols=[ProtocolKind.OPENAI_CHAT.value],
            model_name="z-ai/glm-5.2",
        )
    )
    create_model_group(
        name="glm-client",
        protocols=[client_protocol.value],
        items=[_chat_group_item("z-ai/glm-5.2")],
    )
    key = create_gateway_key()

    response = client.post(
        route,
        headers=gateway_headers(key),
        json={
            "model": "glm-client",
            "max_tokens": 32000,
            "thinking": {"type": "enabled", "budget_tokens": 31999},
            "output_config": {"effort": "max"},
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 502, response.text
    assert captured_body["model"] == "z-ai/glm-5.2"
    assert captured_body["max_tokens"] == 32000
    assert captured_body["thinking"] == {"type": "enabled"}
    assert captured_body["reasoning_effort"] == "max"
    assert "output_config" not in captured_body


def test_openai_chat_stream_logs_kimi_sse_as_json(
    client,
    monkeypatch,
    app_state,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    from lens_api.gateway.service import proxy_upstream, stream_logging

    stream_body = (
        ": keep-alive\n\n"
        'data: {"choices":[{"delta":{"content":"","reasoning":"用户","reasoning_details":[{"format":"unknown","index":0,"text":"用户","type":"reasoning.text"}],"role":"assistant","tool_calls":[{"function":{"arguments":"}"},"index":0}]},"finish_reason":null,"index":0}],"model":"kimi-k3","object":"chat.completion.chunk"}'
        "\n\n"
        'data: {"choices":[{"delta":{"content":"","reasoning":null,"role":"assistant"},"finish_reason":"tool_calls","index":0}],"model":"kimi-k3","object":"chat.completion.chunk"}'
        "\n\n"
        'data: {"choices":[{"delta":{"content":"","role":"assistant"},"finish_reason":"tool_calls","index":0}],"model":"kimi-k3","object":"chat.completion.chunk","usage":{"completion_tokens":346,"prompt_tokens":61105,"total_tokens":61451}}'
        "\n\n"
        "data: [DONE]\n\n"
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
            200,
            content=stream_body.encode(),
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    monkeypatch.setattr(stream_logging, "app_state", app_state)
    run_async(
        app_state.settings_repo.upsert_settings(
            [SettingItem(key=SETTING_RELAY_LOG_BODY_ENABLED, value="true")]
        )
    )
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_CHAT.value],
            model_name="kimi-k3",
        )
    )
    create_model_group(
        name="kimi-k3",
        protocols=[ProtocolKind.OPENAI_CHAT.value],
        items=[_chat_group_item("kimi-k3")],
    )
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "kimi-k3", "messages": [], "stream": True},
    )

    assert response.status_code == 200, response.text
    assert response.text == stream_body
    request_log_item = run_async(
        app_state.request_log_store.list_request_log_page()
    ).items[0]
    request_log = run_async(
        app_state.request_log_store.get_request_log(request_log_item.id)
    )
    assert request_log.input_tokens == 61105
    assert request_log.output_tokens == 346
    assert request_log.total_tokens == 61451
    logged_chunks = json.loads(request_log.response_content or "null")
    assert isinstance(logged_chunks, list)
    assert logged_chunks[0]["choices"][0]["delta"]["reasoning"] == "用户"
