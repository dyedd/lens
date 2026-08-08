from __future__ import annotations

import json
from typing import Any

import httpx
from conftest import gateway_headers, run_async, valid_site_payload

from lens_api.core.runtime_channel_ids import compose_runtime_channel_id
from lens_api.models import ProtocolKind
from lens_api.persistence.shared import SETTING_RELAY_LOG_BODY_ENABLED, SettingItem


def test_chat_proxy_uses_responses_channel_and_converts_response(
    client,
    monkeypatch,
    app_state,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    from lens_api.gateway.service import proxy_upstream

    captured_request: dict[str, Any] = {}

    async def fake_estimate_cost(
        *_args: Any, **_kwargs: Any
    ) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        captured_request["url"] = str(upstream.url)
        captured_request["body"] = json.loads(body_bytes)
        return httpx.Response(
            200,
            json={
                "id": "resp_1",
                "object": "response",
                "created_at": 123,
                "status": "completed",
                "model": "responses-model",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Hello"}],
                    }
                ],
                "usage": {
                    "input_tokens": 3,
                    "output_tokens": 1,
                    "total_tokens": 4,
                },
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    monkeypatch.setattr(
        app_state.model_price_repo, "estimate_model_cost", fake_estimate_cost
    )
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_RESPONSES.value],
            model_name="responses-model",
        )
    )
    create_model_group(
        name="chat-model",
        protocols=[ProtocolKind.OPENAI_CHAT.value],
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_RESPONSES
                ),
                "credential_id": "cred-1",
                "model_name": "responses-model",
                "enabled": True,
            }
        ],
    )
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "chat-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "n": 4,
        },
    )

    assert response.status_code == 200, response.text
    assert captured_request == {
        "url": "https://upstream.example/v1/responses",
        "body": {
            "model": "responses-model",
            "input": [{"role": "user", "content": "Hello"}],
        },
    }
    payload = response.json()
    assert payload["object"] == "chat.completion"
    assert payload["choices"][0]["message"]["content"] == "Hello"
    assert payload["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 1,
        "total_tokens": 4,
    }


def test_streaming_chat_proxy_converts_responses_stream_and_logs_upstream_usage(
    client,
    monkeypatch,
    app_state,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    from lens_api.gateway.service import proxy_upstream, stream_logging

    captured_request: dict[str, Any] = {}

    async def fake_estimate_cost(
        *_args: Any, **_kwargs: Any
    ) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert stream
        captured_request["url"] = str(upstream.url)
        captured_request["body"] = json.loads(body_bytes)
        frames = [
            {
                "type": "response.created",
                "response": {
                    "id": "resp_stream",
                    "created_at": 123,
                    "model": "responses-model",
                },
            },
            {"type": "response.output_text.delta", "delta": "Hello"},
            {
                "type": "response.completed",
                "response": {
                    "id": "resp_stream",
                    "created_at": 123,
                    "status": "completed",
                    "model": "responses-model",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "Hello"}],
                        }
                    ],
                    "usage": {
                        "input_tokens": 5,
                        "output_tokens": 2,
                        "total_tokens": 7,
                    },
                },
            },
        ]
        content = "".join(
            f"event: {frame['type']}\ndata: {json.dumps(frame)}\n\n" for frame in frames
        ).encode()
        return httpx.Response(
            200,
            content=content,
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    monkeypatch.setattr(proxy_upstream, "_safe_estimate_cost", fake_estimate_cost)
    monkeypatch.setattr(stream_logging, "_safe_estimate_cost", fake_estimate_cost)
    monkeypatch.setattr(stream_logging, "app_state", app_state)
    run_async(
        app_state.settings_repo.upsert_settings(
            [SettingItem(key=SETTING_RELAY_LOG_BODY_ENABLED, value="true")]
        )
    )
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_RESPONSES.value],
            model_name="responses-model",
        )
    )
    create_model_group(
        name="chat-model",
        protocols=[ProtocolKind.OPENAI_CHAT.value],
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_RESPONSES
                ),
                "credential_id": "cred-1",
                "model_name": "responses-model",
                "enabled": True,
            }
        ],
    )
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "chat-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
            "stream_options": {"include_usage": True},
            "n": 4,
        },
    )

    assert response.status_code == 200, response.text
    assert captured_request == {
        "url": "https://upstream.example/v1/responses",
        "body": {
            "model": "responses-model",
            "input": [{"role": "user", "content": "Hello"}],
            "stream": True,
        },
    }
    assert '"finish_reason": "stop"' in response.text
    assert '"choices": [], "usage"' in response.text
    assert response.text.endswith("data: [DONE]\n\n")

    request_log_item = run_async(
        app_state.request_log_store.list_request_log_page()
    ).items[0]
    request_log = run_async(
        app_state.request_log_store.get_request_log(request_log_item.id)
    )
    assert request_log.success is True
    assert request_log.status_code == 200
    assert request_log.input_tokens == 5
    assert request_log.output_tokens == 2
    assert request_log.total_tokens == 7
    assert json.loads(request_log.request_content or "null") == captured_request["body"]
    assert '"object": "chat.completion.chunk"' in (request_log.response_content or "")
    assert '"content": "Hello"' in (request_log.response_content or "")
    assert "response.output_text.delta" not in (request_log.response_content or "")
