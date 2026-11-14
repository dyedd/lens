from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from conftest import gateway_headers, valid_site_payload

_PROTOCOLS = ("openai_chat", "openai_responses", "anthropic", "gemini")
_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j0XkAAAAASUVORK5CYII="
_SCHEMA = {
    "type": "object",
    "properties": {"city": {"type": "string"}},
    "required": ["city"],
    "additionalProperties": False,
}


@pytest.mark.parametrize("ttl", [[], {}])
def test_anthropic_cache_hint_ignores_invalid_optional_ttl(
    client, monkeypatch, create_site_group_and_key, ttl
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _, _, key = create_site_group_and_key()

    async def send(_client, upstream, *, stream, body_bytes):
        body = json.loads(body_bytes)
        assert body["messages"][0] == {
            "role": "system",
            "content": "Be brief",
        }
        return httpx.Response(
            200,
            request=httpx.Request("POST", upstream.url),
            json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/messages",
        headers=gateway_headers(key),
        json={
            "model": "gpt-4o",
            "max_tokens": 64,
            "system": [
                {
                    "type": "text",
                    "text": "Be brief",
                    "cache_control": {"type": "ephemeral", "ttl": ttl},
                }
            ],
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["content"][0]["text"] == "ok"


def _client_request(protocol: str, stream: bool) -> tuple[str, dict[str, Any]]:
    if protocol == "openai_chat":
        return "/v1/chat/completions", {
            "model": "public-model",
            "stream": stream,
            "max_completion_tokens": 64,
            "messages": [
                {"role": "system", "content": "Be brief."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Weather?"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{_IMAGE}"},
                        },
                    ],
                },
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call-prev",
                            "type": "function",
                            "function": {
                                "name": "weather",
                                "arguments": '{"city":"Paris"}',
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call-prev",
                    "content": '{"error":"city not found"}',
                },
                {"role": "user", "content": "And Rome?"},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {"name": "weather", "parameters": _SCHEMA},
                }
            ],
        }
    if protocol == "openai_responses":
        return "/v1/responses", {
            "model": "public-model",
            "stream": stream,
            "max_output_tokens": 64,
            "instructions": "Be brief.",
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Weather?"},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/png;base64,{_IMAGE}",
                        },
                    ],
                },
                {
                    "type": "reasoning",
                    "summary": [{"type": "summary_text", "text": "Previous analysis"}],
                    "encrypted_content": "gAAAA-openai-history",
                },
                {
                    "type": "function_call",
                    "call_id": "call-prev",
                    "name": "weather",
                    "arguments": '{"city":"Paris"}',
                },
                {
                    "type": "function_call_output",
                    "call_id": "call-prev",
                    "output": '{"error":"city not found"}',
                },
                {"role": "user", "content": "And Rome?"},
            ],
            "tools": [{"type": "function", "name": "weather", "parameters": _SCHEMA}],
        }
    if protocol == "anthropic":
        return "/v1/messages", {
            "model": "public-model",
            "stream": stream,
            "max_tokens": 64,
            "system": "Be brief.",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Weather?"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": _IMAGE,
                            },
                        },
                    ],
                },
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "Previous analysis",
                            "signature": "lens-foreign-thinking",
                        },
                        {
                            "type": "tool_use",
                            "id": "call-prev",
                            "name": "weather",
                            "input": {"city": "Paris"},
                        },
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call-prev",
                            "content": "city not found",
                            "is_error": True,
                        },
                        {"type": "text", "text": "And Rome?"},
                    ],
                },
            ],
            "tools": [{"name": "weather", "input_schema": _SCHEMA}],
        }
    method = "streamGenerateContent?alt=sse" if stream else "generateContent"
    return f"/v1beta/models/public-model:{method}", {
        "systemInstruction": {"parts": [{"text": "Be brief."}]},
        "generationConfig": {"maxOutputTokens": 64},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": "Weather?"},
                    {"inlineData": {"mimeType": "image/png", "data": _IMAGE}},
                ],
            },
            {
                "role": "model",
                "parts": [
                    {
                        "functionCall": {"name": "weather", "args": {"city": "Paris"}},
                        "thoughtSignature": "gemini#history",
                    }
                ],
            },
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": "weather",
                            "response": {"error": "city not found"},
                        }
                    },
                    {"text": "And Rome?"},
                ],
            },
        ],
        "tools": [
            {
                "functionDeclarations": [
                    {"name": "weather", "parametersJsonSchema": _SCHEMA}
                ]
            }
        ],
    }


def _upstream_response(protocol: str, model: str) -> dict[str, Any]:
    call = {
        "type": "function_call",
        "id": "fc-next",
        "call_id": "call-next",
        "name": "weather",
        "arguments": '{"city":"Rome"}',
        "status": "completed",
    }
    if protocol == "openai_chat":
        return {
            "id": "chat-1",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "Checking",
                        "reasoning_content": "Compare forecasts",
                        "tool_calls": [
                            {
                                "id": "call-next",
                                "type": "function",
                                "function": {
                                    "name": "weather",
                                    "arguments": call["arguments"],
                                },
                            }
                        ],
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 7,
                "total_tokens": 17,
                "prompt_tokens_details": {"cached_tokens": 4, "cache_write_tokens": 2},
                "completion_tokens_details": {"reasoning_tokens": 3},
            },
        }
    if protocol == "openai_responses":
        return {
            "id": "resp-1",
            "object": "response",
            "model": model,
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "id": "msg-1",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "text": "Checking", "annotations": []}
                    ],
                },
                call,
                {
                    "type": "reasoning",
                    "id": "rs-1",
                    "summary": [{"type": "summary_text", "text": "Compare forecasts"}],
                    "encrypted_content": "gAAAA-openai-state",
                },
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 7,
                "total_tokens": 17,
                "input_tokens_details": {"cached_tokens": 4},
                "output_tokens_details": {"reasoning_tokens": 3},
            },
        }
    if protocol == "anthropic":
        return {
            "id": "msg-1",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [
                {"type": "text", "text": "Checking"},
                {
                    "type": "tool_use",
                    "id": "call-next",
                    "name": "weather",
                    "input": {"city": "Rome"},
                },
            ],
            "stop_reason": "tool_use",
            "usage": {
                "input_tokens": 6,
                "cache_read_input_tokens": 4,
                "output_tokens": 7,
            },
        }
    return {
        "responseId": "gemini-1",
        "modelVersion": model,
        "candidates": [
            {
                "index": 0,
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "thought": True,
                            "text": "Compare forecasts",
                            "thoughtSignature": "gemini#thinking",
                        },
                        {"text": "Checking"},
                        {
                            "functionCall": {
                                "id": "call-next",
                                "name": "weather",
                                "args": {"city": "Rome"},
                            },
                            "thoughtSignature": "gemini#next",
                        },
                    ],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 10,
            "cachedContentTokenCount": 4,
            "candidatesTokenCount": 4,
            "thoughtsTokenCount": 3,
            "totalTokenCount": 17,
        },
    }


def _upstream_stream(protocol: str, model: str) -> bytes:
    response = _upstream_response(protocol, model)
    if protocol == "openai_chat":
        frames = [
            {
                "id": "chat-1",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": "Checking",
                            "reasoning_content": "Compare forecasts",
                        },
                    }
                ],
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call-next",
                                    "type": "function",
                                    "function": {
                                        "name": "weather",
                                        "arguments": '{"city":',
                                    },
                                }
                            ]
                        },
                    }
                ]
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "function": {"arguments": '"Rome"}'}}
                            ]
                        },
                    }
                ]
            },
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
            {"choices": [], "usage": response["usage"]},
        ]
    elif protocol == "openai_responses":
        message, call, reasoning = response["output"]
        frames = [
            {"type": "response.created", "response": {"id": "resp-1", "model": model}},
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {**message, "content": []},
            },
            {
                "type": "response.output_text.delta",
                "output_index": 0,
                "content_index": 0,
                "delta": "Checking",
            },
            {"type": "response.output_item.done", "output_index": 0, "item": message},
            {
                "type": "response.output_item.added",
                "output_index": 1,
                "item": {**call, "arguments": ""},
            },
            {
                "type": "response.function_call_arguments.delta",
                "output_index": 1,
                "delta": '{"city":',
            },
            {
                "type": "response.function_call_arguments.delta",
                "output_index": 1,
                "delta": '"Rome"}',
            },
            {"type": "response.output_item.done", "output_index": 1, "item": call},
            {
                "type": "response.output_item.added",
                "output_index": 2,
                "item": {**reasoning, "summary": []},
            },
            {
                "type": "response.reasoning_summary_text.delta",
                "output_index": 2,
                "summary_index": 0,
                "delta": "Compare forecasts",
            },
            {"type": "response.output_item.done", "output_index": 2, "item": reasoning},
            {"type": "response.completed", "response": response},
        ]
    elif protocol == "anthropic":
        frames = [
            {
                "type": "message_start",
                "message": {
                    **response,
                    "content": [],
                    "stop_reason": None,
                    "usage": {
                        "input_tokens": 6,
                        "cache_read_input_tokens": 4,
                        "output_tokens": 0,
                    },
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
                "delta": {"type": "text_delta", "text": "Checking"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "content_block_start",
                "index": 1,
                "content_block": {
                    "type": "tool_use",
                    "id": "call-next",
                    "name": "weather",
                    "input": {},
                },
            },
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "input_json_delta", "partial_json": '{"city":'},
            },
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "input_json_delta", "partial_json": '"Rome"}'},
            },
            {"type": "content_block_stop", "index": 1},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use"},
                "usage": {"output_tokens": 7},
            },
            {"type": "message_stop"},
        ]
    else:
        parts = response["candidates"][0]["content"]["parts"]
        frames = [
            {
                "responseId": "gemini-1",
                "modelVersion": model,
                "candidates": [
                    {"index": 0, "content": {"role": "model", "parts": [part]}}
                ],
            }
            for part in parts
        ]
        frames.extend(
            [
                {"candidates": [{"index": 0, "finishReason": "STOP"}]},
                {"usageMetadata": response["usageMetadata"]},
            ]
        )
    data = "".join(
        (f"event: {frame['type']}\r\n" if "type" in frame else "")
        + "\r\n".join(
            f"data: {line}" for line in json.dumps(frame, indent=2).splitlines()
        )
        + "\r\n\r\n"
        for frame in frames
    )
    if protocol == "openai_chat":
        data += "data: [DONE]\r\n\r\n"
    return data.encode()


class _Chunks(httpx.AsyncByteStream):
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    async def __aiter__(self):
        for offset in range(0, len(self.raw), 17):
            yield self.raw[offset : offset + 17]


def _events(text: str) -> list[dict[str, Any]]:
    result = []
    for frame in text.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(
            line[5:].lstrip() for line in frame.splitlines() if line.startswith("data:")
        )
        if data and data != "[DONE]":
            result.append(json.loads(data))
    return result


def _assert_upstream_request(protocol: str, body: dict[str, Any]) -> None:
    assert _IMAGE in json.dumps(body)
    assert "city not found" in json.dumps(body)
    assert "lens-foreign-thinking" not in json.dumps(body)
    if protocol == "openai_chat":
        calls = [
            call
            for message in body["messages"]
            for call in message.get("tool_calls", [])
        ]
        results = [message for message in body["messages"] if message["role"] == "tool"]
        assert calls[0]["id"] == results[0]["tool_call_id"]
        assert json.loads(calls[0]["function"]["arguments"]) == {"city": "Paris"}
    elif protocol == "openai_responses":
        call = next(
            item for item in body["input"] if item.get("type") == "function_call"
        )
        result = next(
            item for item in body["input"] if item.get("type") == "function_call_output"
        )
        assert call["call_id"] == result["call_id"]
        assert json.loads(call["arguments"]) == {"city": "Paris"}
    elif protocol == "anthropic":
        blocks = [
            part
            for message in body["messages"]
            for part in message["content"]
            if isinstance(part, dict)
        ]
        call = next(part for part in blocks if part.get("type") == "tool_use")
        result = next(part for part in blocks if part.get("type") == "tool_result")
        assert call["id"] == result["tool_use_id"]
        assert call["input"] == {"city": "Paris"}
    else:
        assert "model" not in body and "stream" not in body
        parts = [part for content in body["contents"] for part in content["parts"]]
        call = next(part["functionCall"] for part in parts if "functionCall" in part)
        result = next(
            part["functionResponse"] for part in parts if "functionResponse" in part
        )
        assert call.get("id", call["name"]) == result.get("id", result["name"])
        assert call["args"] == {"city": "Paris"}
        assert (
            body["tools"][0]["functionDeclarations"][0]["parametersJsonSchema"]
            == _SCHEMA
        )


@pytest.mark.parametrize("source", _PROTOCOLS)
@pytest.mark.parametrize("target", _PROTOCOLS)
@pytest.mark.parametrize("stream", [False, True])
def test_protocol_conversion_preserves_tool_history_response_and_usage(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    source,
    target,
    stream,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    model = "gemini-3-flash" if target == "gemini" else "upstream-model"
    create_site(valid_site_payload(protocols=[target], model_name=model))
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": f"pc-1_{target}",
                "credential_id": "cred-1",
                "model_name": model,
                "enabled": True,
            }
        ],
    )
    sent: list[dict[str, Any]] = []

    async def send(_client, upstream, *, stream: bool, body_bytes: bytes):
        body = json.loads(body_bytes)
        _assert_upstream_request(target, body)
        if source == "openai_responses":
            if target == "openai_responses":
                reasoning = next(
                    item for item in body["input"] if item.get("type") == "reasoning"
                )
                assert reasoning == _client_request(source, stream)[1]["input"][1]
            else:
                assert "gAAAA-openai-history" not in json.dumps(body)
        if target == "gemini":
            results = [
                part["functionResponse"]
                for content in body["contents"]
                for part in content["parts"]
                if "functionResponse" in part
            ]
            assert "error" in results[0]["response"]
        if target == "anthropic" and source in {"anthropic", "gemini"}:
            results = [
                part
                for message in body["messages"]
                for part in message["content"]
                if isinstance(part, dict) and part.get("type") == "tool_result"
            ]
            assert results[0]["is_error"] is True
        sent.append(body)
        request = httpx.Request("POST", upstream.url)
        if target == "gemini":
            assert (
                request.url.path
                == f"/v1beta/models/{model}:{'streamGenerateContent' if stream else 'generateContent'}"
            )
            assert request.url.params.get("alt") == ("sse" if stream else None)
            assert upstream.headers["x-goog-api-key"] == "upstream-secret"
        if stream:
            return httpx.Response(
                200,
                stream=_Chunks(_upstream_stream(target, model)),
                headers={"content-type": "text/event-stream"},
                request=request,
            )
        return httpx.Response(
            200, json=_upstream_response(target, model), request=request
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    key = create_gateway_key()
    path, body = _client_request(source, stream)
    headers = (
        {"x-goog-api-key": key["api_key"]}
        if source == "gemini"
        else gateway_headers(key)
    )
    response = client.post(path, headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert len(sent) == 1
    frames = _events(response.text) if stream else [response.json()]
    assert not any("error" in frame for frame in frames), response.text
    if source == "openai_chat":
        text = "".join(
            choice.get("delta" if stream else "message", {}).get("content") or ""
            for frame in frames
            for choice in frame.get("choices", [])
        )
        calls = [
            call
            for frame in frames
            for choice in frame.get("choices", [])
            for call in choice.get("delta" if stream else "message", {}).get(
                "tool_calls", []
            )
        ]
        arguments = "".join(
            call.get("function", {}).get("arguments", "") for call in calls
        )
        assert arguments, response.text
        if stream:
            assert min(call["index"] for call in calls) == 0
        assert text == "Checking"
        assert json.loads(arguments) == {"city": "Rome"}
    elif source == "openai_responses":
        payload = frames[-1]["response"] if stream else frames[0]
        call = next(
            item for item in payload["output"] if item["type"] == "function_call"
        )
        assert json.loads(call["arguments"]) == {"city": "Rome"}
        assert payload["usage"]["input_tokens"] == 10
        assert payload["usage"]["input_tokens_details"]["cached_tokens"] == 4
        if target == "openai_chat":
            assert payload["usage"]["input_tokens_details"]["cache_write_tokens"] == 2
    elif source == "anthropic":
        if target == "openai_responses":
            if stream:
                signatures = [
                    frame["delta"]["signature"]
                    for frame in frames
                    if frame.get("type") == "content_block_delta"
                    and frame["delta"].get("type") == "signature_delta"
                ]
            else:
                signatures = [
                    part.get("signature") or part.get("data")
                    for part in frames[0]["content"]
                    if part["type"] in {"thinking", "redacted_thinking"}
                ]
            assert any(
                value.startswith("lens-responses-reasoning-v1:") for value in signatures
            )
        if stream:
            starts = {
                frame["index"]: frame["content_block"]["type"]
                for frame in frames
                if frame.get("type") == "content_block_start"
            }
            arguments = "".join(
                frame["delta"]["partial_json"]
                for frame in frames
                if frame.get("type") == "content_block_delta"
                and frame["delta"].get("type") == "input_json_delta"
            )
            assert not any(
                frame.get("type") == "content_block_delta"
                and frame["delta"].get("type") == "signature_delta"
                and starts[frame["index"]] == "tool_use"
                for frame in frames
            )
            assert json.loads(arguments) == {"city": "Rome"}
            assert frames[-1]["type"] == "message_stop"
        else:
            call = next(
                part for part in frames[0]["content"] if part["type"] == "tool_use"
            )
            assert call["input"] == {"city": "Rome"}
    else:
        parts = [
            part
            for frame in frames
            for candidate in frame.get("candidates", [])
            for part in candidate.get("content", {}).get("parts", [])
        ]
        call = next(part["functionCall"] for part in parts if "functionCall" in part)
        assert call["args"] == {"city": "Rome"}
        assert frames[-1]["usageMetadata"]["promptTokenCount"] == 10
        assert frames[-1]["usageMetadata"]["cachedContentTokenCount"] == 4
    logs = client.get("/api/admin/request-logs/page", headers=admin_headers).json()[
        "items"
    ]
    assert logs[0]["success"] is True
    assert (
        logs[0]["input_tokens"],
        logs[0]["cache_read_input_tokens"],
        logs[0]["output_tokens"],
    ) == (10, 4, 7)


@pytest.mark.parametrize(
    "model,thinking",
    [
        ("gemini-2.5-pro", {"thinkingBudget": 8192}),
        ("gemini-3-pro", {"thinkingLevel": "HIGH"}),
    ],
)
def test_gemini_converts_structured_output_and_thinking_config(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    model,
    thinking,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    create_site(valid_site_payload(protocols=["gemini"], model_name=model))
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": "pc-1_gemini",
                "credential_id": "cred-1",
                "model_name": model,
                "enabled": True,
            }
        ],
    )

    async def send(_client, upstream, *, stream, body_bytes):
        body = json.loads(body_bytes)
        config = body["generationConfig"]
        assert config["responseJsonSchema"] == _SCHEMA
        assert config["responseMimeType"] == "application/json"
        assert config["thinkingConfig"] == thinking
        return httpx.Response(
            200,
            json={
                "modelVersion": model,
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": '{"city":"Rome"}'}],
                        },
                        "finishReason": "STOP",
                    }
                ],
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "public-model",
            "messages": [{"role": "user", "content": "Choose a city"}],
            "reasoning_effort": "high",
            "max_completion_tokens": 20000,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "city", "schema": _SCHEMA},
            },
        },
    )
    assert response.status_code == 200, response.text
    assert json.loads(response.json()["choices"][0]["message"]["content"]) == {
        "city": "Rome"
    }


@pytest.mark.parametrize("stream", [False, True])
def test_gemini_prompt_filter_returns_a_valid_converted_response(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    stream,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    create_site(valid_site_payload(protocols=["gemini"], model_name="gemini-3-flash"))
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": "pc-1_gemini",
                "credential_id": "cred-1",
                "model_name": "gemini-3-flash",
                "enabled": True,
            }
        ],
    )

    async def send(_client, upstream, *, stream, body_bytes):
        payload = {
            "promptFeedback": {"blockReason": "SAFETY"},
            "usageMetadata": {"promptTokenCount": 10},
        }
        request = httpx.Request("POST", upstream.url)
        if stream:
            raw = f"data: {json.dumps(payload)}\n\n".encode()
            return httpx.Response(
                200,
                stream=_Chunks(raw),
                headers={"content-type": "text/event-stream"},
                request=request,
            )
        return httpx.Response(200, json=payload, request=request)

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "public-model",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": stream,
        },
    )
    assert response.status_code == 200, response.text
    frames = _events(response.text) if stream else [response.json()]
    assert not any("error" in frame for frame in frames), response.text
    usage = next(frame["usage"] for frame in frames if "usage" in frame)
    assert usage["prompt_tokens"] == 10
    assert any(
        choice.get("finish_reason") == "content_filter"
        for frame in frames
        for choice in frame.get("choices", [])
    )
