from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
from conftest import gateway_headers, valid_site_payload

_PIPELINE_PLUGIN = """
import json
from dataclasses import replace
from app.plugins.contract import PluginDefinition, PluginManifest

class Rewrite:
    def extension(self):
        return "request_rewrite"

    async def rewrite(self, body, ctx):
        body["plugin_inbound"] = ctx.request.protocol
        if ctx.request.protocol in {"openai_embedding", "rerank"}:
            body["stream"] = True
        return body

class Credential:
    def extension(self):
        return "upstream_credential"

    def matches(self, call):
        return call.channel.id == "pc-1_" + call.protocol

    async def apply(self, call, ctx):
        call.headers["x-credential-plugin"] = call.channel.id
        return call

class Outbound:
    def extension(self):
        return "upstream_request"

    def matches(self, call):
        return True

    async def apply(self, call, ctx):
        call.headers["x-outbound-plugin"] = call.protocol
        return call

class Reply:
    def extension(self):
        return "upstream_response"

    def matches(self, response):
        return True

    async def apply(self, response, ctx):
        payload = json.loads(response.content)
        payload["plugin_reply"] = response.protocol
        return replace(response, content=json.dumps(payload).encode())

def register(ctx):
    ctx.add_request_rewrite_hook(Rewrite())
    ctx.add_upstream_hook(Credential())
    ctx.add_upstream_hook(Outbound())
    ctx.add_response_hook(Reply())

PLUGIN = PluginDefinition(PluginManifest(id="pipeline", name="Pipeline"), register)
"""


def test_plugins_cover_all_gateway_protocols_and_image_edits(
    client,
    admin_headers,
    monkeypatch,
    install_plugin,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    protocols = [
        "openai_chat",
        "openai_responses",
        "anthropic",
        "gemini",
        "openai_embedding",
        "openai_image",
        "rerank",
    ]
    create_site(valid_site_payload(protocols=protocols, model_name="plugin-model"))
    group = create_model_group(
        name="plugin-model",
        items=[
            {
                "channel_id": "pc-1_" + protocol,
                "credential_id": "cred-1",
                "model_name": "plugin-model",
                "enabled": True,
            }
            for protocol in protocols
        ],
    )
    install_plugin(_PIPELINE_PLUGIN, "pipeline")
    headers = gateway_headers(create_gateway_key())
    sent: list[dict[str, Any]] = []

    async def upstream_reply(_client, upstream, *, stream, body_bytes):
        protocol = upstream.headers["x-outbound-plugin"]
        assert upstream.headers["x-credential-plugin"] == "pc-1_" + protocol
        if "multipart/form-data" in upstream.headers.get("content-type", ""):
            assert b"image.png" in body_bytes and b"image-content" in body_bytes
            assert b"plugin_inbound" in body_bytes
        else:
            payload = json.loads(body_bytes)
            assert payload["plugin_inbound"] == protocol
            if protocol in {"openai_embedding", "rerank"}:
                assert not stream and "stream" not in payload
        sent.append({"protocol": protocol, "url": upstream.url})
        return httpx.Response(
            200,
            json={"model": "plugin-model", "data": []},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", upstream_reply)
    cases = [
        (
            "openai_chat",
            "/v1/chat/completions",
            {"messages": [{"role": "user", "content": "hi"}]},
        ),
        ("openai_responses", "/v1/responses", {"input": "hi"}),
        (
            "anthropic",
            "/v1/messages",
            {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 10},
        ),
        (
            "gemini",
            "/v1beta/models/plugin-model:generateContent",
            {"contents": [{"role": "user", "parts": [{"text": "hi"}]}]},
        ),
        ("openai_embedding", "/v1/embeddings", {"input": "hi"}),
        ("openai_image", "/v1/images/generations", {"prompt": "hi"}),
        ("rerank", "/v1/rerank", {"query": "hi", "documents": ["hi"]}),
    ]
    for protocol, path, body in cases:
        response = client.post(
            path, headers=headers, json={"model": "plugin-model", **body}
        )
        assert response.status_code == 200, response.text
        assert response.json()["plugin_reply"] == protocol
        assert sent[-1]["protocol"] == protocol

    edited = client.post(
        "/v1/images/edits",
        headers=headers,
        data={"model": "plugin-model", "prompt": "edit"},
        files={"image": ("image.png", b"image-content", "image/png")},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["plugin_reply"] == "openai_image"
    assert sent[-1]["url"].endswith("images/edits")

    async def probe_reply(_self, request, **kwargs):
        assert request.headers["x-credential-plugin"] == "pc-1_openai_chat"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}, request=request
        )

    monkeypatch.setattr(httpx.AsyncClient, "send", probe_reply)
    result = client.post(
        f"/api/admin/model-groups/{group['id']}/model-tests",
        headers=admin_headers,
        json={
            "channel_id": "pc-1_openai_chat",
            "credential_id": "cred-1",
            "model_name": "plugin-model",
            "prompt": "hi",
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["success"] is True


_EVENT_PLUGIN = """
from app.plugins.contract import PluginDefinition, PluginManifest

class Event:
    def extension(self):
        return "response_event"

    async def rewrite(self, event, ctx):
        event.data["plugin_event"] = ctx.request.protocol
        return event.data

PLUGIN = PluginDefinition(
    PluginManifest(id="events", name="Events"),
    lambda ctx: ctx.add_response_event_hook(Event()),
)
"""


def test_plugin_events_cover_stream_protocols_and_conversion(
    client,
    monkeypatch,
    install_plugin,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    paths = {
        "openai_chat": "/v1/chat/completions",
        "openai_responses": "/v1/responses",
        "anthropic": "/v1/messages",
        "gemini": "/v1beta/models/{model}:streamGenerateContent?alt=sse",
        "openai_image": "/v1/images/generations",
    }
    upstream_paths = {
        "openai_chat": "chat/completions",
        "openai_responses": "responses",
        "anthropic": "messages",
        "gemini": "models/plugin-model:streamGenerateContent",
        "openai_image": "images/generations",
    }
    create_site(valid_site_payload(protocols=list(paths), model_name="plugin-model"))
    create_model_group(
        name="plugin-model",
        items=[
            {
                "channel_id": "pc-1_" + protocol,
                "credential_id": "cred-1",
                "model_name": "plugin-model",
                "enabled": True,
            }
            for protocol in paths
        ],
    )
    create_model_group(
        name="converted-model",
        items=[
            {
                "channel_id": "pc-1_openai_chat",
                "credential_id": "cred-1",
                "model_name": "plugin-model",
                "enabled": True,
            }
        ],
    )
    install_plugin(_EVENT_PLUGIN, "events")
    headers = gateway_headers(create_gateway_key())
    payloads = {
        "openai_chat": [
            {
                "id": "c1",
                "model": "plugin-model",
                "choices": [
                    {"index": 0, "delta": {"role": "assistant", "content": "hi"}}
                ],
            },
            {
                "id": "c1",
                "model": "plugin-model",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            },
        ],
        "openai_responses": [
            {
                "type": "response.completed",
                "response": {
                    "id": "r1",
                    "model": "plugin-model",
                    "status": "completed",
                    "output": [],
                },
            }
        ],
        "anthropic": [{"type": "message_stop"}],
        "gemini": [
            {
                "modelVersion": "plugin-model",
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "hi"}]},
                        "finishReason": "STOP",
                    }
                ],
            }
        ],
        "openai_image": [{"type": "image_generation.completed", "b64_json": "aGk="}],
    }

    class Chunks(httpx.AsyncByteStream):
        def __init__(self, content):
            self.content = content

        async def __aiter__(self):
            for offset in range(0, len(self.content), 7):
                yield self.content[offset : offset + 7]

    async def upstream_reply(_client, upstream, *, stream, body_bytes):
        assert stream
        protocol = next(
            protocol
            for protocol, path in upstream_paths.items()
            if httpx.URL(upstream.url).path.endswith(path)
        )
        events = payloads[protocol]
        if media_type == "text/event-stream":
            content = ": heartbeat\r\n\r\n" + "".join(
                f"data: {json.dumps(event)}\r\n\r\n" for event in events
            )
            if protocol == "openai_chat":
                content += "data: [DONE]\r\n\r\n"
        else:
            content = "\r\n".join(json.dumps(event) for event in events)
        return httpx.Response(
            200,
            stream=Chunks(content.encode()),
            headers={"content-type": media_type},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", upstream_reply)

    def check_events(protocol, model):
        body = {
            "model": model,
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
            "input": "hi",
            "prompt": "hi",
            "max_tokens": 10,
        }
        if protocol == "gemini":
            body = {"contents": [{"role": "user", "parts": [{"text": "hi"}]}]}
        response = client.post(
            paths[protocol].format(model=model),
            headers=headers,
            json=body,
        )
        assert response.status_code == 200, response.text
        events = [
            json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines()
            if line.startswith("data: {") or line.startswith("{")
        ]
        assert events and all(event["plugin_event"] == protocol for event in events), (
            response.text
        )

    for wire_format in ("sse", "ndjson"):
        media_type = (
            "text/event-stream"
            if wire_format == "sse"
            else "application/x-ndjson; charset=utf-8"
        )
        for protocol in paths:
            check_events(protocol, "plugin-model")
    media_type = "text/event-stream"
    for protocol in ("openai_responses", "anthropic", "gemini"):
        check_events(protocol, "converted-model")


_FAILED_HOOKS_PLUGIN = """
import asyncio
from dataclasses import replace
from app.plugins.contract import PluginDefinition, PluginManifest

class Broken:
    def __init__(self, mode):
        self.mode = mode

    def extension(self):
        return "upstream_request"

    def matches(self, call):
        if self.mode in {"matches", "matches_true"}:
            call.body["messages"][0]["content"] = "broken"
            call.headers["x-broken"] = "yes"
            return self.mode == "matches_true"
        return True

    async def apply(self, call, ctx):
        if self.mode == "matches_true":
            return call
        call.body["messages"][0]["content"] = "broken"
        call.headers["x-broken"] = "yes"
        if self.mode == "none":
            return None
        if self.mode == "error":
            raise ValueError("plugin failed")
        if self.mode == "timeout":
            await asyncio.sleep(1)
        if self.mode == "json":
            return replace(call, body={"bad": object()})
        if self.mode == "unicode":
            return replace(call, body={"bad": chr(0xD800)})
        if self.mode == "url":
            return replace(call, url="https://example.com:invalid")

class Accepted:
    def extension(self):
        return "upstream_request"

    def matches(self, call):
        return True

    async def apply(self, call, ctx):
        call.headers["x-accepted"] = "yes"
        return call

def register(ctx):
    ctx.add_upstream_hook(Accepted())
    for mode in ("matches", "matches_true", "none", "error", "timeout", "json", "unicode", "url"):
        ctx.add_upstream_hook(Broken(mode))

PLUGIN = PluginDefinition(PluginManifest(id="failed_hooks", name="Failed hooks"), register)
"""


def test_failed_plugins_preserve_last_valid_upstream_request(
    client,
    admin_headers,
    monkeypatch,
    install_plugin,
    create_site_group_and_key,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _, _, key = create_site_group_and_key()
    install_plugin(_FAILED_HOOKS_PLUGIN, "failed_hooks")

    async def upstream_reply(_client, upstream, *, stream, body_bytes):
        assert json.loads(body_bytes)["messages"][0]["content"] == "original"
        assert upstream.headers["x-accepted"] == "yes"
        assert "x-broken" not in upstream.headers
        return httpx.Response(
            200, json={"choices": []}, request=httpx.Request("POST", upstream.url)
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", upstream_reply)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "original"}]},
    )
    assert response.status_code == 200, response.text
    plugins = client.get("/api/admin/plugins", headers=admin_headers).json()
    stats = next(plugin for plugin in plugins if plugin["id"] == "failed_hooks")[
        "stats"
    ][0]
    assert stats["failures"] == 5


_LIFETIME_PLUGIN = """
import asyncio
from pathlib import Path
from dataclasses import replace
from app.plugins.contract import PluginDefinition, PluginManifest, PluginSetting

class Hook:
    def __init__(self, path):
        self.path = path
        self.closed = False

    def extension(self):
        return "upstream_response"

    def matches(self, response):
        return True

    async def apply(self, response, ctx):
        if self.closed:
            raise ValueError("resource disposed during request")
        return replace(response, headers={**response.headers, "x-resource": "open"})

    def dispose(self):
        self.closed = True
        self.path.with_suffix(".disposed").touch()

class Observer:
    def __init__(self, hook):
        self.hook = hook

    def extension(self):
        return "request_observer"

    async def completed(self, record):
        self.hook.path.with_suffix(".started").touch()
        while not self.hook.path.with_suffix(".release").exists():
            await asyncio.sleep(0.005)
        self.hook.path.with_suffix(".observed").write_text(str(self.hook.closed))

def register(ctx):
    hook = Hook(Path(ctx.settings["path"]))
    ctx.add_response_hook(hook)
    ctx.add_request_observer(Observer(hook))
    ctx.on_dispose(hook.dispose)

PLUGIN = PluginDefinition(
    PluginManifest(id="lifetime", name="Lifetime", settings=(PluginSetting("path", "Path", default=__PATH__),)),
    register,
)
"""


def test_plugin_disable_waits_for_inflight_request_and_observer(
    client,
    admin_headers,
    monkeypatch,
    tmp_path,
    install_plugin,
    create_site_group_and_key,
) -> None:
    import time

    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    _, _, key = create_site_group_and_key()
    path = tmp_path / "resource"
    install_plugin(_LIFETIME_PLUGIN.replace("__PATH__", repr(str(path))), "lifetime")
    unrelated = tmp_path / "unrelated.disposed"
    install_plugin(
        "from pathlib import Path\n"
        "from app.plugins.contract import PluginDefinition, PluginManifest\n"
        f"def register(ctx):\n    ctx.on_dispose(lambda: Path({str(unrelated)!r}).touch())\n"
        "PLUGIN = PluginDefinition(PluginManifest(id='unrelated', name='Unrelated'), register)\n",
        "unrelated",
    )
    entered, release = threading.Event(), threading.Event()

    async def upstream_reply(_client, upstream, *, stream, body_bytes):
        entered.set()
        await asyncio.to_thread(release.wait, 5)
        return httpx.Response(
            200, json={"choices": []}, request=httpx.Request("POST", upstream.url)
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", upstream_reply)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(
            client.post,
            "/v1/chat/completions",
            headers=gateway_headers(key),
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
        )
        try:
            assert entered.wait(5)
            disabled = client.put(
                "/api/admin/plugins/lifetime",
                headers=admin_headers,
                json={"enabled": False},
            )
            assert disabled.status_code == 200, disabled.text
            assert not path.with_suffix(".disposed").exists()
        finally:
            release.set()
        response = pending.result(timeout=5)
    assert response.status_code == 200, response.text
    assert response.headers["x-resource"] == "open"

    deadline = time.monotonic() + 5
    while not path.with_suffix(".started").exists() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert path.with_suffix(".started").exists()
    assert not path.with_suffix(".disposed").exists()
    disabled = client.put(
        "/api/admin/plugins/unrelated",
        headers=admin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    assert unrelated.exists()
    path.with_suffix(".release").touch()
    while not path.with_suffix(".disposed").exists() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert path.with_suffix(".observed").read_text() == "False"
    assert path.with_suffix(".disposed").exists()
