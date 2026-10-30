from __future__ import annotations

import json
from typing import Any

import httpx
from conftest import gateway_headers, openai_chat_channel_id

_CHAT_REPLY = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 1,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "upstream"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}

_HEADER_PLUGIN = """
from dataclasses import replace

from app.plugins.contract import (
    EXT_UPSTREAM_REQUEST,
    PluginDefinition,
    PluginManifest,
)


class TagRequest:
    def extension(self):
        return EXT_UPSTREAM_REQUEST

    def matches(self, call):
        return True

    async def apply(self, call, ctx):
        return replace(call, headers={**call.headers, "x-plugin-model": call.model_name})


PLUGIN = PluginDefinition(
    manifest=PluginManifest(id="tag_request", name="Tag request"),
    register=lambda context: context.add_upstream_hook(TagRequest()),
)
"""

_REPLY_PLUGIN = """
import json
from dataclasses import replace

from app.plugins.contract import (
    EXT_UPSTREAM_RESPONSE,
    PluginDefinition,
    PluginManifest,
)


class RewriteReply:
    def extension(self):
        return EXT_UPSTREAM_RESPONSE

    def matches(self, response):
        return response.protocol == "openai_chat"

    async def apply(self, response, ctx):
        payload = json.loads(response.content)
        payload["choices"][0]["message"]["content"] = "rewritten"
        return replace(
            response,
            headers={**response.headers, "x-plugin": "reply"},
            content=json.dumps(payload).encode(),
        )


PLUGIN = PluginDefinition(
    manifest=PluginManifest(id="rewrite_reply", name="Rewrite reply"),
    register=lambda context: context.add_response_hook(RewriteReply()),
)
"""

_EVENT_PLUGIN = """
from app.plugins.contract import (
    DROP_EVENT,
    EXT_RESPONSE_EVENT,
    PluginDefinition,
    PluginManifest,
)


class EditEvents:
    def extension(self):
        return EXT_RESPONSE_EVENT

    async def rewrite(self, event, ctx):
        delta = event.data["choices"][0]["delta"]
        if delta.get("content") == "drop":
            return DROP_EVENT
        if delta.get("content") == "old":
            delta["content"] = "new"
            return event.data
        return None


PLUGIN = PluginDefinition(
    manifest=PluginManifest(id="edit_events", name="Edit events"),
    register=lambda context: context.add_response_event_hook(EditEvents()),
)
"""


def _stub_upstream(
    monkeypatch: Any, captured: dict[str, Any], *, content: bytes, media_type: str
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        captured["headers"] = dict(upstream.headers)
        return httpx.Response(
            200,
            content=content,
            headers={"content-type": media_type},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)


def _chat(client: Any, create_gateway_key: Any, **body: Any) -> httpx.Response:
    return client.post(
        "/v1/chat/completions",
        headers=gateway_headers(create_gateway_key()),
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]}
        | body,
    )


def _chat_group(create_site: Any, create_model_group: Any) -> None:
    create_site()
    create_model_group(
        items=[
            {
                "channel_id": openai_chat_channel_id(),
                "credential_id": "cred-1",
                "model_name": "gpt-4o",
                "enabled": True,
            }
        ]
    )


def test_upstream_request_hook_adds_header(
    client,
    monkeypatch,
    install_plugin,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    captured: dict[str, Any] = {}
    _stub_upstream(
        monkeypatch,
        captured,
        content=json.dumps(_CHAT_REPLY).encode(),
        media_type="application/json",
    )
    install_plugin(_HEADER_PLUGIN, "tag_request")
    _chat_group(create_site, create_model_group)

    response = _chat(client, create_gateway_key)

    assert response.status_code == 200, response.text
    assert captured["headers"]["x-plugin-model"] == "gpt-4o"


def test_upstream_response_hook_rewrites_reply(
    client,
    monkeypatch,
    install_plugin,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    _stub_upstream(
        monkeypatch,
        {},
        content=json.dumps(_CHAT_REPLY).encode(),
        media_type="application/json",
    )
    install_plugin(_REPLY_PLUGIN, "rewrite_reply")
    _chat_group(create_site, create_model_group)

    response = _chat(client, create_gateway_key)

    assert response.status_code == 200, response.text
    assert response.headers["x-plugin"] == "reply"
    assert response.json()["choices"][0]["message"]["content"] == "rewritten"


def test_response_event_hook_drops_and_replaces_events(
    client,
    monkeypatch,
    install_plugin,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    chunks = [
        {
            "id": "c1",
            "object": "chat.completion.chunk",
            "model": "gpt-4o",
            "choices": [{"index": 0, "delta": {"content": text}}],
        }
        for text in ("keep", "drop", "old")
    ]
    sse = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
    sse += "data: [DONE]\n\n"
    _stub_upstream(
        monkeypatch, {}, content=sse.encode(), media_type="text/event-stream"
    )
    install_plugin(_EVENT_PLUGIN, "edit_events")
    _chat_group(create_site, create_model_group)

    response = _chat(client, create_gateway_key, stream=True)

    assert response.status_code == 200, response.text
    data = [
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert data[-1] == "[DONE]"
    contents = [
        json.loads(item)["choices"][0]["delta"].get("content") for item in data[:-1]
    ]
    assert contents == ["keep", "new"]
