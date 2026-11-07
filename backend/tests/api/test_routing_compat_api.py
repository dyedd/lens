from __future__ import annotations

import base64
import json
from typing import Any

import httpx
import pytest
from conftest import gateway_headers, valid_site_payload


def _route(create_site, create_model_group, protocol: str, model: str) -> None:
    create_site(valid_site_payload(protocols=[protocol], model_name=model))
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": f"pc-1_{protocol}",
                "credential_id": "cred-1",
                "model_name": model,
                "enabled": True,
            }
        ],
    )


def _upstream_reply(protocol: str, upstream) -> httpx.Response:
    replies = {
        "openai_chat": {
            "model": "upstream-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
        },
        "openai_responses": {
            "id": "resp-compat",
            "model": "upstream-model",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "ok"}],
                }
            ],
        },
        "anthropic": {
            "id": "msg-compat",
            "type": "message",
            "role": "assistant",
            "model": "upstream-model",
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
        },
        "gemini": {
            "modelVersion": "upstream-model",
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": "ok"}]},
                    "finishReason": "STOP",
                }
            ],
        },
    }
    return httpx.Response(
        200,
        json=replies[protocol],
        request=httpx.Request("POST", upstream.url),
    )


@pytest.mark.parametrize(
    "protocol,model",
    [("anthropic", "claude-sonnet-4-5"), ("openai_responses", "gpt-4o")],
)
def test_same_protocol_history_keeps_compatible_sealed_reasoning(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    protocol,
    model,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _route(create_site, create_model_group, protocol, model)
    if protocol == "anthropic":
        kept = [
            {
                "type": "thinking",
                "thinking": "Same provider",
                "signature": base64.urlsafe_b64encode(
                    b"anthropic-sealed-state"
                ).decode(),
            },
            {
                "type": "thinking",
                "thinking": "Unknown provider",
                "signature": "unknown?sealed-state",
            },
            {"type": "text", "text": "Earlier answer"},
        ]
        foreign = [
            {"type": "thinking", "thinking": "Foreign", "signature": "gAAAA-foreign"},
            {
                "type": "redacted_thinking",
                "data": base64.urlsafe_b64encode(b"gemini-sealed-state").decode(),
            },
        ]
        path = "/v1/messages"
        body = {
            "model": "public-model",
            "max_tokens": 64,
            "messages": [
                {"role": "user", "content": "Start"},
                {"role": "assistant", "content": [*kept, *foreign]},
                {"role": "user", "content": "Continue"},
            ],
        }
    else:
        kept = [
            {"type": "reasoning", "encrypted_content": "gAAAA-native", "summary": []},
            {
                "type": "reasoning",
                "encrypted_content": "unknown?sealed-state",
                "summary": [],
            },
            {"role": "user", "content": "Continue"},
        ]
        path = "/v1/responses"
        body = {
            "model": "public-model",
            "input": [
                *kept,
                {
                    "type": "reasoning",
                    "encrypted_content": "claude#foreign",
                    "summary": [],
                },
            ],
        }
    sent: list[dict[str, Any]] = []

    async def send(_client, upstream, *, stream, body_bytes):
        sent.append(json.loads(body_bytes))
        return _upstream_reply(protocol, upstream)

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        path, headers=gateway_headers(create_gateway_key()), json=body
    )
    assert response.status_code == 200, response.text
    assert len(sent) == 1
    assert sent[0]["model"] == model
    if protocol == "anthropic":
        assert sent[0]["messages"] == [
            body["messages"][0],
            {"role": "assistant", "content": kept},
            body["messages"][2],
        ]
    else:
        assert sent[0]["input"] == kept


@pytest.mark.parametrize("protocol", ["openai_chat", "anthropic"])
def test_deepseek_tool_history_includes_empty_thinking(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    protocol,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _route(create_site, create_model_group, protocol, "deepseek-reasoner")
    if protocol == "openai_chat":
        path = "/v1/chat/completions"
        assistant = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-lookup",
                    "type": "function",
                    "function": {"name": "lookup", "arguments": "{}"},
                }
            ],
        }
        tool_result = {"role": "tool", "tool_call_id": "call-lookup", "content": "42"}
        expected = {**assistant, "reasoning_content": ""}
    else:
        path = "/v1/messages"
        call = {"type": "tool_use", "id": "call-lookup", "name": "lookup", "input": {}}
        assistant = {"role": "assistant", "content": [call]}
        tool_result = {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "call-lookup", "content": "42"}
            ],
        }
        expected = {
            "role": "assistant",
            "content": [{"type": "thinking", "thinking": ""}, call],
        }
    sent: list[dict[str, Any]] = []

    async def send(_client, upstream, *, stream, body_bytes):
        sent.append(json.loads(body_bytes))
        return _upstream_reply(protocol, upstream)

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        path,
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "public-model",
            "max_tokens": 64,
            "messages": [
                {"role": "user", "content": "Look up the answer"},
                assistant,
                tool_result,
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert len(sent) == 1
    assert sent[0]["messages"][1:] == [expected, tool_result]


def test_glm_chat_maps_effort_and_keeps_thinking_enabled(
    client, monkeypatch, create_site, create_model_group, create_gateway_key
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _route(create_site, create_model_group, "openai_chat", "zai/GLM-5.2")
    sent: list[dict[str, Any]] = []

    async def send(_client, upstream, *, stream, body_bytes):
        sent.append(json.loads(body_bytes))
        return _upstream_reply("openai_chat", upstream)

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "public-model",
            "messages": [{"role": "user", "content": "Think it through"}],
            "output_config": {"effort": "high"},
            "thinking": {"type": "enabled", "budget_tokens": 8192},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["choices"][0]["message"]["content"] == "ok"
    assert len(sent) == 1
    assert sent[0]["reasoning_effort"] == "high"
    assert sent[0]["thinking"] == {"type": "enabled"}
    assert "output_config" not in sent[0]


@pytest.mark.parametrize(
    "protocol,reasoning_field,reasoning",
    [
        ("openai_chat", "reasoning_effort", "high"),
        ("openai_responses", "reasoning", {"effort": "high"}),
        ("anthropic", "thinking", {"type": "enabled", "budget_tokens": 8192}),
        ("gemini", "generationConfig", {"thinkingLevel": "HIGH"}),
    ],
)
def test_model_effort_suffix_routes_and_configures_each_upstream_protocol(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    protocol,
    reasoning_field,
    reasoning,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _route(create_site, create_model_group, protocol, "upstream-model")
    sent: list[dict[str, Any]] = []

    async def send(_client, upstream, *, stream, body_bytes):
        sent.append(json.loads(body_bytes))
        if protocol == "gemini":
            assert "upstream-model:generateContent" in upstream.url
        return _upstream_reply(protocol, upstream)

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "public-model(high)",
            "messages": [{"role": "user", "content": "Think it through"}],
            "max_completion_tokens": 20000,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["choices"][0]["message"]["content"] == "ok"
    assert len(sent) == 1
    if protocol == "gemini":
        assert sent[0][reasoning_field]["thinkingConfig"] == reasoning
    else:
        assert sent[0]["model"] == "upstream-model"
        assert sent[0][reasoning_field] == reasoning
