from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from conftest import gateway_headers, valid_site_payload
from fastapi.testclient import TestClient

from app.gateway.service.app_state import AppState
from app.gateway.service.privacy_context import PrivacyHistory
from app.gateway.service.proxy import proxy_upstream
from app.gateway.upstream_request import UpstreamRequest
from app.models.settings import SettingItem

EMAIL = "person@example.test"
SECRET = "sk-proj-" + "a1b2c3d4" * 5


def configure(client: Any, admin_headers: dict[str, str], **config: Any) -> None:
    response = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {
                    "key": "privacy_config",
                    "value": json.dumps({"enabled": True, **config}),
                },
                {"key": "relay_log_body_enabled", "value": "true"},
            ]
        },
    )
    assert response.status_code == 200, response.text


def request_body(protocol: str, text: str) -> tuple[str, dict[str, Any]]:
    if protocol == "openai_chat":
        return "/v1/chat/completions", {
            "model": "public-model",
            "messages": [{"role": "user", "content": text}],
        }
    if protocol == "openai_responses":
        return "/v1/responses", {"model": "public-model", "input": text}
    if protocol == "anthropic":
        return "/v1/messages", {
            "model": "public-model",
            "messages": [{"role": "user", "content": text}],
            "max_tokens": 64,
        }
    return "/v1beta/models/public-model:generateContent", {
        "contents": [{"role": "user", "parts": [{"text": text}]}]
    }


def response_body(protocol: str, text: str) -> dict[str, Any]:
    if protocol == "openai_chat":
        return {
            "id": "chat-private",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
    if protocol == "openai_responses":
        return {
            "id": "resp-private",
            "object": "response",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text}],
                }
            ],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    if protocol == "anthropic":
        return {
            "id": "msg-private",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    return {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": text}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
    }


def latest_log(client: Any, headers: dict[str, str]) -> dict[str, Any]:
    logs = client.get("/api/admin/request-logs/page", headers=headers).json()["items"]
    return client.get(
        f"/api/admin/request-logs/{logs[0]['id']}", headers=headers
    ).json()


@pytest.mark.parametrize("ndjson", [False, True])
@pytest.mark.parametrize("legacy_backup", [False, True])
def test_fragmented_stream_logs_and_backups(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site_group_and_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    ndjson: bool,
    legacy_backup: bool,
) -> None:
    configure(client, admin_headers, enabled=not legacy_backup, action="warn")
    _, _, key = create_site_group_and_key()
    output_email = "generated-person@example.test"

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        events = [
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "content": part,
                            "tool_calls": [
                                {"index": 0, "function": {"arguments": argument}}
                            ],
                        },
                    }
                ]
            }
            for part, argument in zip(
                (output_email[:12], output_email[12:]),
                ('{"email":"' + EMAIL[:9], EMAIL[9:] + '"}'),
                strict=True,
            )
        ]
        events.append(
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}
        )
        return httpx.Response(
            200,
            content="".join(
                json.dumps(event) + "\n" if ndjson else f"data: {json.dumps(event)}\n\n"
                for event in events
            ),
            headers={
                "content-type": "application/x-ndjson"
                if ndjson
                else "text/event-stream"
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "gpt-4o",
            "stream": True,
            "messages": [{"role": "user", "content": EMAIL}],
        },
    )
    assert response.status_code == 200, response.text
    if not legacy_backup:
        log = latest_log(client, admin_headers)
        assert log["lifecycle_status"] == "succeeded"
        assert "generated-pe" not in json.dumps(log)
        assert "person@" not in json.dumps(log)
    configure(client, admin_headers)
    exported = client.get(
        "/api/admin/backups/export?include_logs=true", headers=admin_headers
    )
    assert exported.status_code == 200, exported.text
    assert "generated-pe" not in exported.text
    assert "person@" not in exported.text


def test_custom_words_preserve_placeholder_log_values(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site_group_and_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(client, admin_headers, categories=[], words=["LENS", "a"])
    _, _, key = create_site_group_and_key()
    sent: list[str] = []

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        sent.append(json.loads(body_bytes)["messages"][0]["content"])
        return httpx.Response(
            200,
            json=response_body("openai_chat", sent[0]),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "LENS a"}]},
    )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "LENS a"
    log = latest_log(client, admin_headers)
    assert json.loads(log["request_content"])["messages"][0]["content"] == sent[0]
    assert (
        json.loads(log["response_content"])["choices"][0]["message"]["content"]
        == sent[0]
    )


@pytest.mark.parametrize("failure", ["truncated", "interrupted"])
def test_incomplete_stream_log_omits_sensitive_fragments(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site_group_and_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    configure(client, admin_headers, action="warn")
    _, _, key = create_site_group_and_key()
    if failure == "truncated":
        monkeypatch.setattr(
            "app.gateway.service.streaming.capture._STREAM_CONTENT_CAPTURE_LIMIT_BYTES",
            100,
        )

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        events = [
            {"choices": [{"index": 0, "delta": {"content": "generated-person@"}}]}
        ]
        if failure == "truncated":
            events.append(
                {
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": "example.test"},
                            "finish_reason": "stop",
                        }
                    ]
                }
            )
        else:
            events.append({"error": {"message": "upstream interrupted"}})
        return httpx.Response(
            200,
            content="".join(f"data: {json.dumps(event)}\n\n" for event in events),
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "gpt-4o",
            "stream": True,
            "messages": [{"role": "user", "content": EMAIL}],
        },
    )
    assert response.status_code == 200
    log = latest_log(client, admin_headers)
    assert "generated-person" not in json.dumps(log)
    assert "omitted" in log["response_content"]


def test_html_error_is_cleaned_before_summary_truncation(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site_group_and_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_word = "classified-business-value-" + "x" * 180
    configure(client, admin_headers, words=[private_word])
    _, _, key = create_site_group_and_key()

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        return httpx.Response(
            400,
            text="<html><title>" + "error " * 20 + private_word + "</title></html>",
            headers={"content-type": "text/html"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 400
    assert "classified-business" not in response.text
    assert "classified-business" not in json.dumps(latest_log(client, admin_headers))


@pytest.mark.parametrize(
    "client_protocol", ["openai_chat", "openai_responses", "anthropic", "gemini"]
)
@pytest.mark.parametrize(
    "upstream_protocol", ["openai_chat", "openai_responses", "anthropic", "gemini"]
)
def test_mask_round_trip_and_logs(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site: Callable[..., dict[str, Any]],
    create_model_group: Callable[..., dict[str, Any]],
    create_gateway_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    client_protocol: str,
    upstream_protocol: str,
) -> None:
    configure(client, admin_headers)
    create_site(
        valid_site_payload(protocols=[upstream_protocol], model_name="native-model")
    )
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": f"pc-1_{upstream_protocol}",
                "credential_id": "cred-1",
                "model_name": "native-model",
                "enabled": True,
            }
        ],
    )

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        serialized = body_bytes.decode()
        assert EMAIL not in serialized and SECRET not in serialized
        tokens = re.findall(r"\[\[LENS_[A-Z]+_[0-9a-f]{32}\]\]", serialized)
        assert len(tokens) >= 2
        return httpx.Response(
            200,
            json=response_body(upstream_protocol, " ".join(tokens)),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    path, body = request_body(client_protocol, EMAIL + " " + SECRET)
    response = client.post(
        path, headers=gateway_headers(create_gateway_key()), json=body
    )
    assert response.status_code == 200, response.text
    assert EMAIL in response.text and SECRET in response.text
    log = latest_log(client, admin_headers)
    assert EMAIL not in json.dumps(log) and SECRET not in json.dumps(log)
    assert sum(hit["count"] for hit in log["privacy_summary"]) == 2


@pytest.mark.parametrize("action", ["mask", "warn", "block"])
def test_actions_and_preview_isolation(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site_group_and_key: Callable[..., dict[str, Any]],
    app_state: AppState,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    configure(client, admin_headers, action=action)
    _, _, key = create_site_group_and_key()
    sent = []

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        sent.append(body_bytes.decode())
        return httpx.Response(
            200,
            json=response_body("openai_chat", "ok"),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": EMAIL}]},
    )
    assert response.status_code == (400 if action == "block" else 200), response.text
    assert len(sent) == (0 if action == "block" else 1)
    if sent:
        assert (EMAIL in sent[0]) == (action == "warn")
    assert EMAIL not in json.dumps(latest_log(client, admin_headers))
    count = len(app_state.privacy_history.entries)
    preview = client.post(
        "/api/admin/settings/privacy/preview",
        headers=admin_headers,
        json={"text": EMAIL, "config": {"enabled": True}},
    )
    assert preview.status_code == 200, preview.text
    assert EMAIL not in preview.text
    assert len(app_state.privacy_history.entries) == count
    assert (
        client.post(
            "/api/admin/settings/privacy/preview", json={"text": EMAIL}
        ).status_code
        == 401
    )


@pytest.mark.parametrize("pattern", ["(", "a*", "(?=private)", "x" * 513])
def test_invalid_rules_rejected(
    client: TestClient, admin_headers: dict[str, str], pattern: str
) -> None:
    response = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {
                    "key": "privacy_config",
                    "value": json.dumps(
                        {"enabled": True, "regex_rules": [{"pattern": pattern}]}
                    ),
                }
            ]
        },
    )
    assert response.status_code == 400, response.text


@pytest.mark.parametrize(
    "text",
    [
        SECRET,
        "password=hunter22",
        '密码="测试秘密"',
        "a@b.example",
        "+8613812345678",
        "11010519491231002X",
        "4111 1111 1111 1111",
        "postgres://user:pass@db.example/data",
        "-----BEGIN PRIVATE KEY-----\nabcdef\n-----END PRIVATE KEY-----",
        "eyJabcdefghijk.abcdefghijklmnop.qrstuvwxyzabcdefgh",
    ],
)
def test_builtin_rules_preview(
    client: TestClient, admin_headers: dict[str, str], text: str
) -> None:
    preview = client.post(
        "/api/admin/settings/privacy/preview",
        headers=admin_headers,
        json={"text": text, "config": {"enabled": True}},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["hits"]
    assert preview.json()["text"] != text


def test_custom_rules_exceptions_and_timeout(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site_group_and_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = {
        "enabled": True,
        "categories": [],
        "words": ["private-project"],
        "regex_rules": [{"pattern": "customer-[0-9]+"}],
        "exceptions": ["customer-42"],
    }
    preview = client.post(
        "/api/admin/settings/privacy/preview",
        headers=admin_headers,
        json={"text": "private-project customer-11 customer-42", "config": config},
    ).json()
    assert preview["hits"][0]["count"] == 2
    assert "customer-42" in preview["text"]
    assert "customer-11" not in preview["text"]
    configure(client, admin_headers, categories=[], regex_rules=[{"pattern": "(a+)+$"}])
    _, _, key = create_site_group_and_key()
    sent = []

    async def send(*args: Any, **kwargs: Any) -> httpx.Response:
        sent.append(True)
        raise AssertionError("Detection failure must not reach upstream")

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "a" * 100000 + "!"}],
        },
    )
    assert response.status_code == 400
    assert "privacy_error" in response.text
    assert not sent
    assert "a" * 100 not in json.dumps(latest_log(client, admin_headers))


@pytest.mark.parametrize(
    ("protocol", "tool_type", "streaming"),
    [
        ("openai_chat", "function", False),
        ("openai_responses", "function_call", False),
        ("anthropic", "tool_use", False),
        ("anthropic", "server_tool_use", False),
        ("anthropic", "mcp_tool_use", False),
        ("anthropic", "tool_use", True),
        ("anthropic", "server_tool_use", True),
        ("anthropic", "mcp_tool_use", True),
        ("gemini", "functionCall", False),
    ],
)
def test_tool_content_preserves_structure(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site: Callable[..., dict[str, Any]],
    create_model_group: Callable[..., dict[str, Any]],
    create_gateway_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    protocol: str,
    tool_type: str,
    streaming: bool,
) -> None:
    configure(client, admin_headers)
    create_site(valid_site_payload(protocols=[protocol], model_name="native-model"))
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": f"pc-1_{protocol}",
                "credential_id": "cred-1",
                "model_name": "native-model",
                "enabled": True,
            }
        ],
    )
    arguments = {
        "model": EMAIL,
        "type": SECRET,
        "name": EMAIL,
        "id": EMAIL,
        "nested": {"password": "otherwise-unrecognized"},
    }
    schema = {
        "type": "object",
        "properties": {"model": {"type": "string", "enum": [EMAIL]}},
    }
    path, body = request_body(protocol, "hello")
    body["stream"] = streaming
    if protocol == "openai_chat":
        body["system"] = EMAIL
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "store",
                    "description": EMAIL,
                    "parameters": schema,
                },
            }
        ]
        body["messages"] += [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "store",
                            "arguments": json.dumps(arguments),
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": SECRET},
        ]
    elif protocol == "openai_responses":
        body["instructions"] = EMAIL
        body["tools"] = [
            {
                "type": "function",
                "name": "store",
                "description": EMAIL,
                "parameters": schema,
            }
        ]
        body["input"] = [
            {
                "type": "function_call",
                "name": "store",
                "call_id": "call_1",
                "arguments": json.dumps(arguments),
            },
            {"type": "function_call_output", "call_id": "call_1", "output": SECRET},
        ]
    elif protocol == "anthropic":
        body["system"] = [{"type": "text", "text": EMAIL}]
        body["tools"] = [
            {"name": "store", "description": EMAIL, "input_schema": schema}
        ]
        body["messages"] += [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": tool_type,
                        "id": "call_1",
                        "name": "store",
                        "input": arguments,
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "call_1", "content": SECRET}
                ],
            },
        ]
    else:
        body["systemInstruction"] = {"parts": [{"text": EMAIL}]}
        body["tools"] = [
            {
                "functionDeclarations": [
                    {"name": "store", "description": EMAIL, "parameters": schema}
                ]
            }
        ]
        body["contents"] += [
            {
                "role": "model",
                "parts": [{"functionCall": {"name": "store", "args": arguments}}],
            },
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": "store",
                            "response": {"content": SECRET},
                        }
                    }
                ],
            },
        ]

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        outgoing = json.loads(body_bytes)
        serialized = json.dumps(outgoing)
        assert serialized.count(EMAIL) == 1
        assert SECRET not in serialized and "otherwise-unrecognized" not in serialized
        assert '"name": "store"' in serialized
        assert '"model": "native-model"' in serialized or protocol == "gemini"
        result = response_body(protocol, "ok")
        if protocol == "anthropic":
            result["content"] = outgoing["messages"][1]["content"]
            if stream:
                events = [
                    {"type": "message_start", "message": {**result, "content": []}},
                    {
                        "type": "content_block_start",
                        "index": 0,
                        "content_block": result["content"][0],
                    },
                    {"type": "content_block_stop", "index": 0},
                    {"type": "message_delta", "delta": {"stop_reason": "tool_use"}},
                    {"type": "message_stop"},
                ]
                return httpx.Response(
                    200,
                    content="".join(
                        f"data: {json.dumps(event)}\n\n" for event in events
                    ),
                    headers={"content-type": "text/event-stream"},
                    request=httpx.Request("POST", upstream.url),
                )
        return httpx.Response(
            200,
            json=result,
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        path, headers=gateway_headers(create_gateway_key()), json=body
    )
    assert response.status_code == 200, response.text
    if protocol == "anthropic":
        if streaming:
            events = [
                json.loads(line[6:])
                for line in response.text.splitlines()
                if line.startswith("data: ")
            ]
            restored = next(
                event["content_block"]
                for event in events
                if event.get("type") == "content_block_start"
            )
        else:
            restored = response.json()["content"][0]
        assert restored["type"] == tool_type
        assert restored["input"] == arguments


@pytest.mark.parametrize("action", ["mask", "warn", "block"])
@pytest.mark.parametrize("exempt", [False, True])
def test_session_recognizes_previously_detected_value(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site_group_and_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    exempt: bool,
) -> None:
    original = "cedar-lantern-42"
    configure(client, admin_headers)
    _, _, key = create_site_group_and_key()
    sent: list[str] = []

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        text = json.loads(body_bytes)["messages"][0]["content"]
        sent.append(text)
        return httpx.Response(
            200,
            json=response_body("openai_chat", text),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    headers = {**gateway_headers(key), "x-lens-session-id": "known-secret"}
    body = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": f"secret = {original}"}],
    }
    response = client.post("/v1/chat/completions", headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert original in response.text and original not in sent[0]
    token = sent[0].removeprefix("secret = ")

    configure(
        client,
        admin_headers,
        action=action,
        exceptions=[original] if exempt else [],
    )
    body["messages"][0]["content"] = f"Use {original} when connecting."
    response = client.post("/v1/chat/completions", headers=headers, json=body)
    if action == "block" and not exempt:
        assert response.status_code == 400, response.text
        assert len(sent) == 1
    else:
        assert response.status_code == 200, response.text
        expected = original if action == "warn" or exempt else token
        assert sent[1] == f"Use {expected} when connecting."
        assert original in response.text
    if not exempt:
        log = latest_log(client, admin_headers)
        assert original not in json.dumps(log)
        assert log["privacy_summary"][0]["action"] == action


@pytest.mark.parametrize("vendor_text", ["vendor-context", "vendor@example.test"])
def test_signed_gemini_function_call_roundtrip(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site: Callable[..., dict[str, Any]],
    create_model_group: Callable[..., dict[str, Any]],
    create_gateway_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    app_state: AppState,
    vendor_text: str,
) -> None:
    configure(client, admin_headers)
    create_site(valid_site_payload(protocols=["gemini"], model_name="native-model"))
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": "pc-1_gemini",
                "credential_id": "cred-1",
                "model_name": "native-model",
                "enabled": True,
            }
        ],
    )
    vendor_part = None
    calls = 0

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        nonlocal vendor_part, calls
        calls += 1
        outgoing = json.loads(body_bytes)
        if calls == 1:
            token = outgoing["contents"][0]["parts"][0]["text"]
            vendor_part = {
                "functionCall": {
                    "name": "store",
                    "args": {"email": token, "vendor": vendor_text},
                },
                "thoughtSignature": "signature-private",
            }
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {"role": "model", "parts": [vendor_part]},
                            "finishReason": "STOP",
                        }
                    ]
                },
                request=httpx.Request("POST", upstream.url),
            )
        assert outgoing["contents"][1]["parts"][0] == vendor_part
        return httpx.Response(
            200,
            json=response_body("gemini", "ok"),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    key = create_gateway_key()
    path, body = request_body("gemini", EMAIL)
    response = client.post(path, headers=gateway_headers(key), json=body)
    assert response.status_code == 200, response.text
    returned = response.json()["candidates"][0]["content"]
    assert returned["parts"][0]["functionCall"]["args"] == {
        "email": EMAIL,
        "vendor": vendor_text,
    }
    body["contents"].append(returned)
    response = client.post(path, headers=gateway_headers(key), json=body)
    if vendor_text == "vendor@example.test":
        assert response.status_code == 400, response.text
        assert calls == 1
        return
    assert response.status_code == 200, response.text
    other_key = create_gateway_key(remark="other")
    assert (
        client.post(path, headers=gateway_headers(other_key), json=body).status_code
        == 400
    )
    app_state.privacy_history.entries.clear()
    assert client.post(path, headers=gateway_headers(key), json=body).status_code == 400
    assert calls == 2


@pytest.mark.parametrize("ndjson", [False, True])
def test_stream_parallel_tools_and_json_escaping(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site_group_and_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    ndjson: bool,
) -> None:
    original = 'value "quoted" \\ path 汉字'
    configure(client, admin_headers, words=[original])
    _, _, key = create_site_group_and_key()

    class ByteStream(httpx.AsyncByteStream):
        def __init__(self, content: bytes) -> None:
            self.content = content

        async def __aiter__(self) -> AsyncIterator[bytes]:
            for offset in range(0, len(self.content), 7):
                yield self.content[offset : offset + 7]

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        token = json.loads(body_bytes)["messages"][0]["content"]
        events = []
        for index in (0, 1):
            events.append(
                {
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": index,
                                        "id": f"call_{index}",
                                        "type": "function",
                                        "function": {
                                            "name": "store",
                                            "arguments": '{"value":"' + token[:12],
                                        },
                                    }
                                ]
                            },
                        }
                    ]
                }
            )
        for index in (1, 0):
            events.append(
                {
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": index,
                                        "function": {"arguments": token[12:] + '"}'},
                                    }
                                ]
                            },
                        }
                    ]
                }
            )
        events.append(
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}
        )
        wire = (
            (
                "\n".join(json.dumps(event, ensure_ascii=False) for event in events)
                + "\n"
            )
            if ndjson
            else "".join(
                f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events
            )
            + "data: [DONE]\n\n"
        )
        return httpx.Response(
            200,
            stream=ByteStream(wire.encode()),
            headers={
                "content-type": "application/x-ndjson"
                if ndjson
                else "text/event-stream"
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "gpt-4o",
            "stream": True,
            "messages": [{"role": "user", "content": original}],
        },
    )
    assert response.status_code == 200, response.text
    arguments = {0: "", 1: ""}
    for line in response.text.splitlines():
        text = line.removeprefix("data: ")
        if not text or text == "[DONE]":
            continue
        event = json.loads(text)
        assert "error" not in event, event
        for choice in event.get("choices", []):
            for tool in choice.get("delta", {}).get("tool_calls", []):
                arguments[tool["index"]] += tool.get("function", {}).get(
                    "arguments", ""
                )
    assert all(json.loads(value) == {"value": original} for value in arguments.values())
    log = latest_log(client, admin_headers)
    assert log["lifecycle_status"] == "succeeded"
    assert original not in json.dumps(log, ensure_ascii=False)


def test_response_reference_session_and_key_isolation(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site: Callable[..., dict[str, Any]],
    create_model_group: Callable[..., dict[str, Any]],
    create_gateway_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    app_state: AppState,
) -> None:
    configure(client, admin_headers)
    create_site(
        valid_site_payload(protocols=["openai_responses"], model_name="native-model")
    )
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": "pc-1_openai_responses",
                "credential_id": "cred-1",
                "model_name": "native-model",
                "enabled": True,
            }
        ],
    )
    token = ""
    calls = 0

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        nonlocal token, calls
        calls += 1
        outgoing = json.loads(body_bytes)
        if calls == 1:
            token = outgoing["input"]
        return httpx.Response(
            200,
            json=response_body("openai_responses", token),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    key = create_gateway_key()
    path, body = request_body("openai_responses", EMAIL)
    headers = {**gateway_headers(key), "x-lens-session-id": "session-a"}
    assert EMAIL in client.post(path, headers=headers, json=body).text
    followup = {
        "model": "public-model",
        "input": "continue",
        "previous_response_id": "resp-private",
    }
    assert EMAIL in client.post(path, headers=headers, json=followup).text
    assert (
        client.post(
            path,
            headers={**gateway_headers(key), "x-lens-session-id": "session-b"},
            json=followup,
        ).status_code
        == 400
    )
    other = create_gateway_key(remark="other")
    assert (
        client.post(path, headers=gateway_headers(other), json=followup).status_code
        == 400
    )
    forged = {"model": "public-model", "input": token}
    response = client.post(path, headers=gateway_headers(other), json=forged)
    assert token in response.text and EMAIL not in response.text
    app_state.privacy_history.entries.clear()
    assert client.post(path, headers=headers, json=followup).status_code == 400


def test_parameter_override_and_retry_mapping(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site: Callable[..., dict[str, Any]],
    create_model_group: Callable[..., dict[str, Any]],
    create_gateway_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    app_state: AppState,
) -> None:
    configure(client, admin_headers)
    members = []
    for index in (1, 2):
        create_site(
            valid_site_payload(
                name=f"Site {index}",
                base_id=f"base-{index}",
                credential_id=f"cred-{index}",
                protocol_config_id=f"pc-{index}",
                model_name="native-model",
            )
        )
        members.append(
            {
                "channel_id": f"pc-{index}_openai_chat",
                "credential_id": f"cred-{index}",
                "model_name": "native-model",
                "enabled": True,
            }
        )
    create_model_group(name="public-model", items=members)
    override = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {
                    "key": "upstream_param_override_config",
                    "value": json.dumps(
                        {
                            "rules": [
                                {
                                    "path": "messages.0.content",
                                    "action": "set",
                                    "value": SECRET,
                                }
                            ]
                        }
                    ),
                }
            ]
        },
    )
    assert override.status_code == 200, override.text
    calls = []

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        calls.append(json.loads(body_bytes))
        assert EMAIL not in body_bytes.decode() and SECRET not in body_bytes.decode()
        if len(calls) == 1:
            await app_state.settings_repo.upsert_settings(
                [
                    SettingItem(
                        key="privacy_config",
                        value=json.dumps({"enabled": True, "action": "block"}),
                    )
                ]
            )
            return httpx.Response(
                500,
                json={"error": {"message": SECRET + " " + EMAIL}},
                request=httpx.Request("POST", upstream.url),
            )
        assert calls[0]["messages"] == calls[1]["messages"]
        return httpx.Response(
            200,
            json=response_body("openai_chat", calls[-1]["messages"][-1]["content"]),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    path, body = request_body("openai_chat", EMAIL)
    response = client.post(
        path, headers=gateway_headers(create_gateway_key()), json=body
    )
    assert response.status_code == 200, response.text
    assert SECRET in response.text
    log = latest_log(client, admin_headers)
    assert len(log["attempts"]) == 2
    assert SECRET not in json.dumps(log) and EMAIL not in json.dumps(log)


@pytest.mark.parametrize(
    "protocol,path,body",
    [
        ("openai_embedding", "/v1/embeddings", {"input": [EMAIL, SECRET]}),
        ("rerank", "/v1/rerank", {"query": EMAIL, "documents": [{"text": SECRET}]}),
        ("openai_image", "/v1/images/generations", {"prompt": EMAIL}),
        ("openai_image", "/v1/images/edits", {"prompt": EMAIL}),
    ],
)
def test_additional_endpoints(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site: Callable[..., dict[str, Any]],
    create_model_group: Callable[..., dict[str, Any]],
    create_gateway_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    protocol: str,
    path: str,
    body: dict[str, Any],
) -> None:
    configure(client, admin_headers)
    create_site(valid_site_payload(protocols=[protocol], model_name="native-model"))
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": f"pc-1_{protocol}",
                "credential_id": "cred-1",
                "model_name": "native-model",
                "enabled": True,
            }
        ],
    )

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert EMAIL.encode() not in body_bytes and SECRET.encode() not in body_bytes
        assert b"[[LENS_" in body_bytes
        if path.endswith("edits"):
            assert b"binary-image-untouched" in body_bytes
        return httpx.Response(
            200,
            json={"data": [], "results": [], "usage": {"prompt_tokens": 1}},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    arguments = (
        {
            "data": {"model": "public-model", **body},
            "files": {"image": ("image.png", b"binary-image-untouched", "image/png")},
        }
        if path.endswith("edits")
        else {"json": {"model": "public-model", **body}}
    )
    response = client.post(
        path, headers=gateway_headers(create_gateway_key()), **arguments
    )
    assert response.status_code == 200, response.text


def test_backups_scrub_logs_and_preserve_privacy_on_legacy_import(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site_group_and_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = "cedar-lantern-42"
    _, _, key = create_site_group_and_key()
    client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={"items": [{"key": "relay_log_body_enabled", "value": "true"}]},
    )

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=response_body("openai_chat", f"Use {original} when connecting."),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": f"secret = {original}"}],
        },
    )
    assert response.status_code == 200
    assert original in json.dumps(latest_log(client, admin_headers))
    configure(client, admin_headers)
    exported = client.get(
        "/api/admin/backups/export?include_logs=true", headers=admin_headers
    )
    assert exported.status_code == 200, exported.text
    assert original not in exported.text
    assert original in json.dumps(latest_log(client, admin_headers))
    dump = exported.json()
    dump["settings"] = [
        entry for entry in dump["settings"] if entry["key"] != "privacy_config"
    ]
    dump["settings"].append({"key": "plugins_config", "value": "{}"})
    dump["request_logs"][0]["request_content"] = f"secret = {original}"
    dump["request_logs"][0]["response_content"] = f"Use {original} when connecting."
    dump["request_logs"][0].pop("privacy_summary", None)
    imported = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("legacy.json", json.dumps(dump).encode(), "application/json")},
    )
    assert imported.status_code == 200, imported.text
    assert original not in json.dumps(latest_log(client, admin_headers))
    settings = client.get("/api/admin/settings", headers=admin_headers).json()
    assert (
        json.loads(
            next(
                entry["value"] for entry in settings if entry["key"] == "privacy_config"
            )
        )["enabled"]
        is True
    )


@pytest.mark.parametrize("protocol", ["anthropic", "openai_responses", "gemini"])
@pytest.mark.parametrize("convert_to_chat", [False, True])
@pytest.mark.parametrize("action", ["mask", "warn"])
def test_native_stream_text_across_events(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site: Callable[..., dict[str, Any]],
    create_model_group: Callable[..., dict[str, Any]],
    create_gateway_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    protocol: str,
    convert_to_chat: bool,
    action: str,
) -> None:
    configure(client, admin_headers, action=action)
    create_site(valid_site_payload(protocols=[protocol], model_name="native-model"))
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": f"pc-1_{protocol}",
                "credential_id": "cred-1",
                "model_name": "native-model",
                "enabled": True,
            }
        ],
    )

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        token = (
            EMAIL
            if action == "warn"
            else re.search(
                r"\[\[LENS_[A-Z]+_[0-9a-f]{32}\]\]", body_bytes.decode()
            ).group()
        )
        if protocol == "anthropic":
            events = [
                {
                    "type": "message_start",
                    "message": {
                        "id": "msg-stream",
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "usage": {"input_tokens": 1, "output_tokens": 0},
                    },
                },
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
                *[
                    {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": part},
                    }
                    for part in (token[:17], token[17:])
                ],
                {"type": "content_block_stop", "index": 0},
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn"},
                    "usage": {"output_tokens": 1},
                },
                {"type": "message_stop"},
            ]
        elif protocol == "openai_responses":
            events = [
                *[
                    {
                        "type": "response.output_text.delta",
                        "item_id": "item_1",
                        "output_index": 0,
                        "content_index": 0,
                        "delta": part,
                    }
                    for part in (token[:17], token[17:])
                ],
                {
                    "type": "response.completed",
                    "response": response_body(protocol, token),
                },
            ]
        else:
            events = [
                {
                    "candidates": [
                        {"index": 0, "content": {"parts": [{"text": token[:17]}]}}
                    ]
                },
                {
                    "candidates": [
                        {
                            "index": 0,
                            "content": {"parts": [{"text": token[17:]}]},
                            "finishReason": "STOP",
                        }
                    ]
                },
            ]
        return httpx.Response(
            200,
            content="".join(
                f"data: {json.dumps(event)}\n\n: heartbeat\n\n" for event in events
            ),
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    path, body = request_body("openai_chat" if convert_to_chat else protocol, EMAIL)
    body["stream"] = True
    path = path.replace(":generateContent", ":streamGenerateContent?alt=sse")
    response = client.post(
        path, headers=gateway_headers(create_gateway_key()), json=body
    )
    assert response.status_code == 200, response.text
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]
    if convert_to_chat:
        text = "".join(
            choice.get("delta", {}).get("content", "")
            for event in events
            for choice in event.get("choices", [])
        )
    elif protocol == "anthropic":
        text = "".join(event.get("delta", {}).get("text", "") for event in events)
    elif protocol == "openai_responses":
        text = "".join(
            event["delta"]
            for event in events
            if event.get("type") == "response.output_text.delta"
        )
    else:
        text = "".join(
            part.get("text", "")
            for event in events
            for candidate in event.get("candidates", [])
            for part in candidate.get("content", {}).get("parts", [])
        )
    assert text == EMAIL
    assert "[[LENS_" not in response.text
    log = latest_log(client, admin_headers)
    assert log["lifecycle_status"] == "succeeded"
    assert EMAIL not in json.dumps(log) and "person@" not in json.dumps(log)


@pytest.mark.parametrize("ndjson", [False, True])
@pytest.mark.parametrize("closed_json", [False, True])
def test_incomplete_tool_placeholder_fails_without_health_penalty(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site_group_and_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    ndjson: bool,
    closed_json: bool,
) -> None:
    configure(client, admin_headers)
    _, _, key = create_site_group_and_key()

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        token = json.loads(body_bytes)["messages"][0]["content"]
        events = [
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "store",
                                        "arguments": '{"value":"'
                                        + token[:22]
                                        + ('"}' if closed_json else ""),
                                    },
                                }
                            ]
                        },
                    }
                ]
            },
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
        ]
        return httpx.Response(
            200,
            content=("\n".join(json.dumps(event) for event in events) + "\n")
            if ndjson
            else "".join(f"data: {json.dumps(event)}\n\n" for event in events),
            headers={
                "content-type": "application/x-ndjson"
                if ndjson
                else "text/event-stream"
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "gpt-4o",
            "stream": True,
            "messages": [{"role": "user", "content": EMAIL}],
        },
    )
    if ndjson:
        frames = [json.loads(line) for line in response.text.splitlines() if line]
        assert frames[-1]["error"]["type"] == "privacy_error"
    assert "privacy" in response.text.lower()
    assert '"finish_reason":"tool_calls"' not in response.text
    assert latest_log(client, admin_headers)["lifecycle_status"] == "failed"
    routes = client.get("/api/admin/routes", headers=admin_headers).json()
    assert not any(entry.get("last_error_category") for entry in routes["health"])


def test_stream_preserves_literal_brackets(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site_group_and_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(client, admin_headers)
    _, _, key = create_site_group_and_key()

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        token = json.loads(body_bytes)["messages"][0]["content"]
        events = [
            {"choices": [{"index": 0, "delta": {"content": part, "reasoning": part}}]}
            for part in (token[:2], token[2:], " literal [")
        ]
        events.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        return httpx.Response(
            200,
            content="".join(f"data: {json.dumps(event)}\n\n" for event in events)
            + "data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "gpt-4o",
            "stream": True,
            "messages": [{"role": "user", "content": EMAIL}],
        },
    )
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]
    assert all("error" not in event for event in events), response.text
    assert (
        "".join(
            choice.get("delta", {}).get("content", "")
            for event in events
            for choice in event.get("choices", [])
        )
        == EMAIL + " literal ["
    )
    assert (
        "".join(
            choice.get("delta", {}).get("reasoning", "")
            for event in events
            for choice in event.get("choices", [])
        )
        == EMAIL + " literal ["
    )


@pytest.mark.parametrize("protocol", ["anthropic", "gemini"])
@pytest.mark.parametrize(
    ("initial_action", "replay_action"),
    [("mask", "mask"), ("warn", "mask"), ("warn", "block")],
)
def test_stream_signed_content_replay(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site: Callable[..., dict[str, Any]],
    create_model_group: Callable[..., dict[str, Any]],
    create_gateway_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    protocol: str,
    initial_action: str,
    replay_action: str,
) -> None:
    configure(client, admin_headers, action=initial_action)
    create_site(valid_site_payload(protocols=[protocol], model_name="native-model"))
    create_model_group(
        name="public-model",
        items=[
            {
                "channel_id": f"pc-1_{protocol}",
                "credential_id": "cred-1",
                "model_name": "native-model",
                "enabled": True,
            }
        ],
    )
    signed = {}
    calls = []

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        outgoing = json.loads(body_bytes)
        calls.append(outgoing)
        if not stream:
            replay = (
                outgoing["messages"][1]["content"][0]
                if protocol == "anthropic"
                else outgoing["contents"][1]["parts"][0]
            )
            assert replay == signed
            return httpx.Response(
                200,
                json=response_body(protocol, "ok"),
                request=httpx.Request("POST", upstream.url),
            )
        token = (
            EMAIL
            if initial_action == "warn"
            else re.search(
                r"\[\[LENS_[A-Z]+_[0-9a-f]{32}\]\]", body_bytes.decode()
            ).group()
        )
        if protocol == "anthropic":
            signed.update(
                {
                    "type": "thinking",
                    "thinking": token + " vendor-context",
                    "signature": "sig-stream",
                }
            )
            events = [
                {
                    "type": "message_start",
                    "message": {
                        "id": "msg-stream",
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                    },
                },
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "thinking", "thinking": ""},
                },
                *[
                    {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "thinking_delta", "thinking": part},
                    }
                    for part in (token[:10], token[10:] + " vendor-context")
                ],
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "signature_delta", "signature": "sig-stream"},
                },
                {"type": "content_block_stop", "index": 0},
                {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
                {"type": "message_stop"},
            ]
        else:
            signed.update(
                {
                    "functionCall": {
                        "name": "store",
                        "args": {"email": token, "vendor": "vendor-context"},
                    },
                    "thoughtSignature": "sig-stream",
                }
            )
            events = [
                {
                    "candidates": [
                        {
                            "index": 0,
                            "content": {"parts": [{"text": "Calling a tool."}]},
                        }
                    ]
                },
                {
                    "candidates": [
                        {
                            "index": 0,
                            "content": {"parts": [signed]},
                            "finishReason": "STOP",
                        }
                    ]
                },
            ]
        return httpx.Response(
            200,
            content="".join(f"data: {json.dumps(event)}\n\n" for event in events),
            headers={"content-type": "text/event-stream"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    key = create_gateway_key()
    path, body = request_body(protocol, EMAIL)
    stream_path = path.replace(":generateContent", ":streamGenerateContent?alt=sse")
    response = client.post(
        stream_path, headers=gateway_headers(key), json={**body, "stream": True}
    )
    if protocol == "anthropic":
        thinking = "".join(
            json.loads(line[6:]).get("delta", {}).get("thinking", "")
            for line in response.text.splitlines()
            if line.startswith("data: ")
        )
        assert thinking == EMAIL + " vendor-context"
    else:
        assert EMAIL in response.text, response.text
    assert "sig-stream" in response.text
    configure(client, admin_headers, action=replay_action)
    path, body = request_body(protocol, "continue")
    if protocol == "anthropic":
        body["messages"].append(
            {
                "role": "assistant",
                "content": [{**signed, "thinking": EMAIL + " vendor-context"}],
            }
        )
    else:
        body["contents"].append(
            {
                "role": "model",
                "parts": [
                    {
                        **signed,
                        "functionCall": {
                            "name": "store",
                            "args": {"email": EMAIL, "vendor": "vendor-context"},
                        },
                    }
                ],
            }
        )
    response = client.post(path, headers=gateway_headers(key), json=body)
    if initial_action == "warn":
        assert response.status_code == 400, response.text
        assert "privacy" in response.json()["error"]["message"].lower()
        assert len(calls) == 1
    else:
        assert response.status_code == 200, response.text
        assert len(calls) == 2


def test_stream_session_history_and_active_request_survive_eviction(
    client: TestClient,
    admin_headers: dict[str, str],
    create_site_group_and_key: Callable[..., dict[str, Any]],
    create_gateway_key: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    app_state: AppState,
) -> None:
    configure(client, admin_headers)
    _, _, key = create_site_group_and_key()
    token = ""
    calls = 0

    async def send(
        _client: httpx.AsyncClient,
        upstream: UpstreamRequest,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        nonlocal token, calls
        calls += 1
        if calls == 1:
            token = json.loads(body_bytes)["messages"][0]["content"]
            events = [
                {"choices": [{"index": 0, "delta": {"content": token}}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ]
            return httpx.Response(
                200,
                content="".join(f"data: {json.dumps(event)}\n\n" for event in events),
                headers={"content-type": "text/event-stream"},
                request=httpx.Request("POST", upstream.url),
            )
        if calls == 2:
            app_state.privacy_history = PrivacyHistory()
        return httpx.Response(
            200,
            json=response_body("openai_chat", token),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    headers = {**gateway_headers(key), "x-lens-session-id": "session-a"}
    body = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": EMAIL}],
        "stream": True,
    }
    assert EMAIL in client.post("/v1/chat/completions", headers=headers, json=body).text
    body = {"model": "gpt-4o", "messages": [{"role": "user", "content": "continue"}]}
    assert EMAIL in client.post("/v1/chat/completions", headers=headers, json=body).text
    response = client.post(
        "/v1/chat/completions",
        headers={**gateway_headers(key), "x-lens-session-id": "session-b"},
        json=body,
    )
    assert EMAIL not in response.text and token in response.text
    response = client.post(
        "/v1/chat/completions",
        headers={
            **gateway_headers(create_gateway_key(remark="other")),
            "x-lens-session-id": "session-a",
        },
        json=body,
    )
    assert EMAIL not in response.text and token in response.text
