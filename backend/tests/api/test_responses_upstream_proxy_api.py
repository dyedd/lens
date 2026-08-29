from __future__ import annotations

import json
from typing import Any

import httpx
from conftest import gateway_headers, run_async, valid_site_payload

from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.protocols import ProtocolKind
from app.models.settings import SettingItem
from app.persistence.repositories.model_price_repository import ModelCostEstimate
from app.persistence.settings_keys import SETTING_RELAY_LOG_BODY_ENABLED

_RESPONSES_CHANNEL_ID = compose_runtime_channel_id(
    "pc-1", ProtocolKind.OPENAI_RESPONSES
)


async def _no_cost(*_args: Any, **_kwargs: Any) -> ModelCostEstimate:
    return ModelCostEstimate()


def _responses_channel(
    create_site: Any,
    create_model_group: Any,
    *,
    client_protocol: ProtocolKind,
    group_name: str,
) -> None:
    """Point a client-protocol group at a single OpenAI Responses upstream."""
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.OPENAI_RESPONSES.value],
            model_name="responses-model",
        )
    )
    create_model_group(
        name=group_name,
        items=[
            {
                "channel_id": _RESPONSES_CHANNEL_ID,
                "credential_id": "cred-1",
                "model_name": "responses-model",
                "enabled": True,
            }
        ],
    )


def _stub_upstream(
    monkeypatch: Any,
    captured: dict[str, Any],
    *,
    json_body: dict[str, Any] | None = None,
    sse_frames: list[dict[str, Any]] | None = None,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert stream is (sse_frames is not None)
        captured["url"] = str(upstream.url)
        captured["body"] = json.loads(body_bytes)
        request = httpx.Request("POST", upstream.url)
        if sse_frames is None:
            return httpx.Response(200, json=json_body, request=request)
        content = "".join(
            f"event: {frame['type']}\ndata: {json.dumps(frame)}\n\n"
            for frame in sse_frames
        ).encode()
        return httpx.Response(
            200,
            content=content,
            headers={"content-type": "text/event-stream"},
            request=request,
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)


def _enable_body_logging(monkeypatch: Any, app_state: Any) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream
    import app.gateway.service.stream_logging as stream_logging

    monkeypatch.setattr(proxy_upstream, "_safe_estimate_cost", _no_cost)
    monkeypatch.setattr(stream_logging, "_safe_estimate_cost", _no_cost)
    monkeypatch.setattr(stream_logging, "app_state", app_state)
    run_async(
        app_state.settings_repo.upsert_settings(
            [SettingItem(key=SETTING_RELAY_LOG_BODY_ENABLED, value="true")]
        )
    )


def _latest_request_log(app_state: Any) -> Any:
    item = run_async(app_state.request_log_store.list_request_log_page()).items[0]
    return run_async(app_state.request_log_store.get_request_log(item.id))


def _completed_frames() -> list[dict[str, Any]]:
    message = {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "Hello"}],
    }
    return [
        {
            "type": "response.created",
            "response": {
                "id": "resp_stream",
                "created_at": 123,
                "model": "responses-model",
            },
        },
        {
            "type": "response.output_text.delta",
            "output_index": 0,
            "content_index": 0,
            "delta": "Hello",
        },
        {"type": "response.output_item.done", "output_index": 0, "item": message},
        {
            "type": "response.completed",
            "response": {
                "id": "resp_stream",
                "created_at": 123,
                "status": "completed",
                "model": "responses-model",
                "output": [message],
                "usage": {
                    "input_tokens": 5,
                    "output_tokens": 2,
                    "total_tokens": 7,
                },
            },
        },
    ]


def test_chat_proxy_uses_responses_channel_and_converts_response(
    client,
    monkeypatch,
    app_state,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    captured: dict[str, Any] = {}
    _stub_upstream(
        monkeypatch,
        captured,
        json_body={
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
            "usage": {"input_tokens": 3, "output_tokens": 1, "total_tokens": 4},
        },
    )
    monkeypatch.setattr(app_state.model_price_repo, "estimate_model_cost", _no_cost)
    _responses_channel(
        create_site,
        create_model_group,
        client_protocol=ProtocolKind.OPENAI_CHAT,
        group_name="chat-model",
    )

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "chat-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "n": 4,
        },
    )

    assert response.status_code == 200, response.text
    assert captured == {
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


def test_anthropic_proxy_uses_responses_channel_and_converts_response(
    client,
    monkeypatch,
    app_state,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    captured: dict[str, Any] = {}
    _stub_upstream(
        monkeypatch,
        captured,
        json_body={
            "id": "resp_1",
            "status": "completed",
            "model": "responses-model",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Hello"}],
                }
            ],
            "usage": {"input_tokens": 3, "output_tokens": 1, "total_tokens": 4},
        },
    )
    monkeypatch.setattr(app_state.model_price_repo, "estimate_model_cost", _no_cost)
    _responses_channel(
        create_site,
        create_model_group,
        client_protocol=ProtocolKind.ANTHROPIC,
        group_name="anthropic-model",
    )

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "anthropic-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
        },
    )

    assert response.status_code == 200, response.text
    assert captured == {
        "url": "https://upstream.example/v1/responses",
        "body": {
            "model": "responses-model",
            "input": [{"role": "user", "content": "Hello"}],
            "max_output_tokens": 100,
            "store": False,
        },
    }
    assert response.json() == {
        "id": "resp_1",
        "type": "message",
        "role": "assistant",
        "model": "responses-model",
        "content": [{"type": "text", "text": "Hello"}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 3, "output_tokens": 1},
    }


def test_streaming_chat_proxy_converts_responses_stream_and_logs_upstream_usage(
    client,
    monkeypatch,
    app_state,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    captured: dict[str, Any] = {}
    _stub_upstream(monkeypatch, captured, sse_frames=_completed_frames())
    _enable_body_logging(monkeypatch, app_state)
    _responses_channel(
        create_site,
        create_model_group,
        client_protocol=ProtocolKind.OPENAI_CHAT,
        group_name="chat-model",
    )

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "chat-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
            "stream_options": {"include_usage": True},
            "n": 4,
        },
    )

    assert response.status_code == 200, response.text
    assert captured == {
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

    request_log = _latest_request_log(app_state)
    assert request_log.success is True
    assert request_log.status_code == 200
    assert request_log.input_tokens == 5
    assert request_log.output_tokens == 2
    assert request_log.total_tokens == 7
    assert json.loads(request_log.request_content or "null") == captured["body"]
    logged_chunks = json.loads(request_log.response_content or "null")
    assert isinstance(logged_chunks, list)
    assert any(
        chunk.get("object") == "chat.completion.chunk" for chunk in logged_chunks
    )
    assert any(
        choice.get("delta", {}).get("content") == "Hello"
        for chunk in logged_chunks
        for choice in chunk.get("choices", [])
    )
    assert "response.output_text.delta" not in (request_log.response_content or "")


def test_streaming_anthropic_proxy_converts_responses_stream_and_logs_usage(
    client,
    monkeypatch,
    app_state,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    captured: dict[str, Any] = {}
    _stub_upstream(monkeypatch, captured, sse_frames=_completed_frames())
    _enable_body_logging(monkeypatch, app_state)
    _responses_channel(
        create_site,
        create_model_group,
        client_protocol=ProtocolKind.ANTHROPIC,
        group_name="anthropic-model",
    )

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "anthropic-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
            "stream": True,
        },
    )

    assert response.status_code == 200, response.text
    assert captured["url"] == "https://upstream.example/v1/responses"
    assert captured["body"]["stream"] is True
    assert '"type": "text_delta", "text": "Hello"' in response.text
    assert '"input_tokens": 5, "output_tokens": 2' in response.text
    assert response.text.endswith(
        'event: message_stop\ndata: {"type": "message_stop"}\n\n'
    )

    request_log = _latest_request_log(app_state)
    assert request_log.success is True
    assert request_log.input_tokens == 5
    assert request_log.output_tokens == 2
    assert request_log.total_tokens == 7
    assert "response.output_text.delta" not in (request_log.response_content or "")
