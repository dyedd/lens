from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import httpx
import pytest
from conftest import gateway_headers, valid_site_payload

_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}
_RAW_INPUT = ' \n{"input":"literal tool text"}\n '
_CALLS = [
    ("call-search", "docs__search", {"query": "Lens"}),
    ("call-patch", "docs__apply_patch", {"input": _RAW_INPUT}),
    ("call-literal", "literal__tool", {"value": 1}),
]


def _upstream_reply(
    protocol: str, calls: Sequence[tuple[str, str, dict[str, Any]]] = ()
) -> dict[str, Any]:
    if protocol == "openai_chat":
        return {
            "id": "chat-tools",
            "model": "upstream-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "ok",
                        "tool_calls": [
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(arguments),
                                },
                            }
                            for call_id, name, arguments in calls
                        ],
                    },
                    "finish_reason": "tool_calls" if calls else "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
    if protocol == "anthropic":
        return {
            "id": "msg-tools",
            "type": "message",
            "role": "assistant",
            "model": "upstream-model",
            "content": [
                {"type": "text", "text": "ok"},
                *[
                    {
                        "type": "tool_use",
                        "id": call_id,
                        "name": name,
                        "input": arguments,
                    }
                    for call_id, name, arguments in calls
                ],
            ],
            "stop_reason": "tool_use" if calls else "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    if protocol == "openai_responses":
        return {
            "id": "resp-format",
            "model": "upstream-model",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "ok"}],
                }
            ],
        }
    return {
        "responseId": "gemini-tools",
        "modelVersion": "upstream-model",
        "candidates": [
            {
                "index": 0,
                "content": {
                    "role": "model",
                    "parts": [
                        {"text": "ok"},
                        *[
                            {
                                "functionCall": {
                                    "id": call_id,
                                    "name": name,
                                    "args": arguments,
                                }
                            }
                            for call_id, name, arguments in calls
                        ],
                    ],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 1,
            "candidatesTokenCount": 1,
            "totalTokenCount": 2,
        },
    }


def _upstream_stream(protocol: str) -> bytes:
    if protocol == "gemini":
        frames = [_upstream_reply(protocol, _CALLS)]
    elif protocol == "openai_chat":
        frames = []
        for index, (call_id, name, arguments) in enumerate(_CALLS):
            encoded = json.dumps(arguments)
            for position, piece in enumerate((encoded[:8], encoded[8:])):
                call = {"index": index, "function": {"arguments": piece}}
                if position == 0:
                    call.update(id=call_id, type="function")
                    call["function"]["name"] = name
                frames.append(
                    {
                        "id": "chat-tools",
                        "model": "upstream-model",
                        "choices": [{"index": 0, "delta": {"tool_calls": [call]}}],
                    }
                )
        frames.append(
            {
                "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        )
    else:
        frames = [
            {
                "type": "message_start",
                "message": {
                    "id": "msg-tools",
                    "model": "upstream-model",
                    "content": [],
                    "usage": {"input_tokens": 1},
                },
            }
        ]
        for index, (call_id, name, arguments) in enumerate(_CALLS):
            frames.append(
                {
                    "type": "content_block_start",
                    "index": index,
                    "content_block": {
                        "type": "tool_use",
                        "id": call_id,
                        "name": name,
                        "input": {},
                    },
                }
            )
            encoded = json.dumps(arguments)
            frames.extend(
                {
                    "type": "content_block_delta",
                    "index": index,
                    "delta": {"type": "input_json_delta", "partial_json": piece},
                }
                for piece in (encoded[:8], encoded[8:])
            )
            frames.append({"type": "content_block_stop", "index": index})
        frames.extend(
            [
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "tool_use"},
                    "usage": {"output_tokens": 1},
                },
                {"type": "message_stop"},
            ]
        )
    content = "".join(f"data: {json.dumps(frame)}\n\n" for frame in frames)
    if protocol == "openai_chat":
        content += "data: [DONE]\n\n"
    return content.encode()


class _Chunks(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def __aiter__(self):
        for offset in range(0, len(self.content), 11):
            yield self.content[offset : offset + 11]


def _route(create_site, create_model_group, target: str) -> None:
    create_site(valid_site_payload(protocols=[target], model_name="upstream-model"))
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": f"pc-1_{target}",
                "credential_id": "cred-1",
                "model_name": "upstream-model",
                "enabled": True,
            }
        ],
    )


@pytest.mark.parametrize("target", ["openai_chat", "anthropic", "gemini"])
@pytest.mark.parametrize("stream", [False, True])
def test_responses_custom_and_namespaced_tools_round_trip(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    target,
    stream,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _route(create_site, create_model_group, target)
    sent: list[dict[str, Any]] = []

    async def send(_client, upstream, *, stream: bool, body_bytes: bytes):
        sent.append(json.loads(body_bytes))
        request = httpx.Request("POST", upstream.url)
        if stream:
            return httpx.Response(
                200,
                stream=_Chunks(_upstream_stream(target)),
                headers={"content-type": "text/event-stream"},
                request=request,
            )
        return httpx.Response(
            200, json=_upstream_reply(target, _CALLS), request=request
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/responses",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "public-model",
            "stream": stream,
            "input": [
                {"role": "user", "content": "Apply this change"},
                {
                    "type": "custom_tool_call",
                    "call_id": "call-prev",
                    "name": "apply_patch",
                    "namespace": "docs",
                    "input": _RAW_INPUT,
                },
                {
                    "type": "custom_tool_call_output",
                    "call_id": "call-prev",
                    "output": "applied",
                },
            ],
            "tools": [
                {
                    "type": "namespace",
                    "name": "docs",
                    "tools": [
                        {
                            "type": "function",
                            "name": "search",
                            "parameters": {"type": "object"},
                        },
                        {"type": "custom", "name": "apply_patch"},
                    ],
                },
                {
                    "type": "function",
                    "name": "literal__tool",
                    "parameters": {"type": "object"},
                },
            ],
        },
    )
    assert response.status_code == 200, response.text
    if stream:
        frames = [
            json.loads(line[6:])
            for line in response.text.splitlines()
            if line.startswith("data: {")
        ]
        payload = frames[-1]["response"]
        custom_delta = [
            frame["delta"]
            for frame in frames
            if frame["type"] == "response.custom_tool_call_input.delta"
        ]
        custom_done = [
            frame["input"]
            for frame in frames
            if frame["type"] == "response.custom_tool_call_input.done"
        ]
        assert "".join(custom_delta) == _RAW_INPUT
        assert custom_done == [_RAW_INPUT]
    else:
        payload = response.json()
    calls = {
        item["name"]: item
        for item in payload["output"]
        if item["type"] in {"function_call", "custom_tool_call"}
    }
    assert set(calls) == {"search", "apply_patch", "literal__tool"}
    assert calls["search"]["namespace"] == "docs"
    assert json.loads(calls["search"]["arguments"]) == {"query": "Lens"}
    assert calls["apply_patch"]["namespace"] == "docs"
    assert calls["apply_patch"]["type"] == "custom_tool_call"
    assert calls["apply_patch"]["input"] == _RAW_INPUT
    assert "namespace" not in calls["literal__tool"]
    assert json.loads(calls["literal__tool"]["arguments"]) == {"value": 1}
    body = sent[0]
    if target == "openai_chat":
        history = next(
            message["tool_calls"][0]
            for message in body["messages"]
            if message.get("tool_calls")
        )
        assert json.loads(history["function"]["arguments"]) == {"input": _RAW_INPUT}
    elif target == "anthropic":
        history = next(
            part
            for message in body["messages"]
            if isinstance(message["content"], list)
            for part in message["content"]
            if part["type"] == "tool_use"
        )
        assert history["input"] == {"input": _RAW_INPUT}
    else:
        history = next(
            part["functionCall"]
            for message in body["contents"]
            for part in message["parts"]
            if "functionCall" in part
        )
        assert history["args"] == {"input": _RAW_INPUT}


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("anthropic", "openai_chat"),
        ("anthropic", "openai_responses"),
        ("anthropic", "gemini"),
        ("openai_chat", "anthropic"),
        ("openai_responses", "anthropic"),
    ],
)
def test_structured_output_and_reasoning_effort_survive_conversion(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    source,
    target,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _route(create_site, create_model_group, target)
    sent: list[dict[str, Any]] = []

    async def send(_client, upstream, *, stream: bool, body_bytes: bytes):
        sent.append(json.loads(body_bytes))
        return httpx.Response(
            200,
            json=_upstream_reply(target),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    if source == "anthropic":
        path = "/v1/messages"
        body = {
            "messages": [{"role": "user", "content": "Answer"}],
            "max_tokens": 64,
            "thinking": {"type": "adaptive"},
            "output_config": {
                "effort": "high",
                "format": {"type": "json_schema", "schema": _SCHEMA},
            },
        }
    elif source == "openai_chat":
        path = "/v1/chat/completions"
        body = {
            "messages": [{"role": "user", "content": "Answer"}],
            "reasoning_effort": "high",
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "answer", "schema": _SCHEMA},
            },
        }
    else:
        path = "/v1/responses"
        body = {
            "input": "Answer",
            "reasoning": {"effort": "high"},
            "text": {
                "format": {"type": "json_schema", "name": "answer", "schema": _SCHEMA}
            },
        }
    response = client.post(
        path,
        headers=gateway_headers(create_gateway_key()),
        json={"model": "public-model", **body},
    )
    assert response.status_code == 200, response.text
    upstream_body = sent[0]
    if target == "anthropic":
        assert upstream_body["output_config"] == {
            "effort": "high",
            "format": {"type": "json_schema", "schema": _SCHEMA},
        }
    elif target == "openai_chat":
        assert upstream_body["response_format"]["json_schema"]["schema"] == _SCHEMA
        assert upstream_body["reasoning_effort"] == "high"
    elif target == "openai_responses":
        assert upstream_body["text"]["format"]["schema"] == _SCHEMA
        assert upstream_body["reasoning"]["effort"] == "high"
    else:
        assert upstream_body["generationConfig"]["responseJsonSchema"] == _SCHEMA
        assert (
            upstream_body["generationConfig"]["thinkingConfig"]["thinkingLevel"]
            == "HIGH"
        )


@pytest.mark.parametrize("source", ["openai_chat", "openai_responses"])
def test_forced_tools_keep_parallel_calls_disabled(
    client, monkeypatch, create_site, create_model_group, create_gateway_key, source
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _route(create_site, create_model_group, "anthropic")
    sent: list[dict[str, Any]] = []

    async def send(_client, upstream, *, stream: bool, body_bytes: bytes):
        sent.append(json.loads(body_bytes))
        return httpx.Response(
            200,
            json=_upstream_reply("anthropic"),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    headers = gateway_headers(create_gateway_key())
    for mode in ("auto", "required", "function"):
        if source == "openai_chat":
            path = "/v1/chat/completions"
            choice = (
                {"type": "function", "function": {"name": "lookup"}}
                if mode == "function"
                else mode
            )
            body = {
                "messages": [{"role": "user", "content": "Look up"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup",
                            "parameters": {"type": "object"},
                        },
                    }
                ],
            }
        else:
            path = "/v1/responses"
            choice = (
                {"type": "function", "name": "lookup"} if mode == "function" else mode
            )
            body = {
                "input": "Look up",
                "tools": [
                    {
                        "type": "function",
                        "name": "lookup",
                        "parameters": {"type": "object"},
                    }
                ],
            }
        response = client.post(
            path,
            headers=headers,
            json={
                "model": "public-model",
                "tool_choice": choice,
                "parallel_tool_calls": False,
                **body,
            },
        )
        assert response.status_code == 200, response.text
        expected = {
            "type": {"auto": "auto", "required": "any", "function": "tool"}[mode],
            "disable_parallel_tool_use": True,
        }
        if mode == "function":
            expected["name"] = "lookup"
        assert sent[-1]["tool_choice"] == expected
        assert "parallel_tool_calls" not in sent[-1]


def test_namespaced_tool_collisions_are_rejected_before_upstream(
    client, monkeypatch, create_site, create_model_group, create_gateway_key
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _route(create_site, create_model_group, "openai_chat")
    sent: list[dict[str, Any]] = []

    async def send(_client, upstream, *, stream: bool, body_bytes: bytes):
        sent.append(json.loads(body_bytes))
        return httpx.Response(
            200,
            json=_upstream_reply("openai_chat"),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/responses",
        headers=gateway_headers(create_gateway_key()),
        json={
            "model": "public-model",
            "input": "Search",
            "tools": [
                {
                    "type": "namespace",
                    "name": "docs",
                    "tools": [
                        {
                            "type": "function",
                            "name": "search",
                            "parameters": {"type": "object"},
                        }
                    ],
                },
                {
                    "type": "function",
                    "name": "docs__search",
                    "parameters": {"type": "object"},
                },
            ],
        },
    )
    assert response.status_code == 400, response.text
    assert "Tool names collide" in response.json()["error"]["message"]
    assert not sent
