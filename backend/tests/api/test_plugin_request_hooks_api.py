from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx
from conftest import gateway_headers

from app.persistence.repositories.model_price_repository import ModelCostEstimate

REWRITE_PLUGIN = """
import json

from app.plugins.contract import (
    EXT_REQUEST_REWRITE,
    PluginContext,
    PluginDefinition,
    PluginManifest,
    PluginRejection,
)


class Guard:
    def extension(self) -> str:
        return EXT_REQUEST_REWRITE

    async def rewrite(self, body, ctx):
        if "forbidden phrase" in json.dumps(body["messages"]):
            raise PluginRejection(451, "Blocked by policy")
        body["messages"].insert(0, {"role": "system", "content": "Be brief."})
        return body


def register(context: PluginContext) -> None:
    context.add_request_rewrite_hook(Guard())


PLUGIN = PluginDefinition(
    manifest=PluginManifest(id="guard", name="Guard"),
    register=register,
)
"""

OBSERVER_PLUGIN = """
import dataclasses
import json

from app.plugins.contract import (
    EXT_REQUEST_OBSERVER,
    PluginContext,
    PluginDefinition,
    PluginManifest,
    PluginSetting,
)


class Recorder:
    def __init__(self, path: str) -> None:
        self.path = path

    def extension(self) -> str:
        return EXT_REQUEST_OBSERVER

    async def completed(self, record) -> None:
        if not self.path:
            return
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(dataclasses.asdict(record)) + "\\n")


def register(context: PluginContext) -> None:
    context.add_request_observer(Recorder(context.settings["path"]))


PLUGIN = PluginDefinition(
    manifest=PluginManifest(
        id="recorder",
        name="Recorder",
        settings=(PluginSetting(key="path", label="Path"),),
    ),
    register=register,
)
"""

_CHAT_REPLY = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hi"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
}


async def _no_cost(*_args: Any, **_kwargs: Any) -> ModelCostEstimate:
    return ModelCostEstimate()


def _stub_upstream(monkeypatch: Any, sent: list[dict[str, Any]]) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        sent.append(json.loads(body_bytes))
        request = httpx.Request("POST", upstream.url)
        if not stream:
            return httpx.Response(200, json=_CHAT_REPLY, request=request)
        chunk = {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "model": "gpt-4o",
            "choices": [
                {"index": 0, "delta": {"content": "Hi"}, "finish_reason": "stop"}
            ],
        }
        return httpx.Response(
            200,
            content=f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode(),
            headers={"content-type": "text/event-stream"},
            request=request,
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    monkeypatch.setattr(proxy_upstream, "safe_estimate_cost", _no_cost)


def _chat(client: Any, key: dict[str, Any], text: str, **extra: Any) -> Any:
    return client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": text}]}
        | extra,
    )


def test_request_rewrite_changes_upstream_body_and_rejects_in_protocol(
    client, monkeypatch, install_plugin, create_site_group_and_key
) -> None:
    sent: list[dict[str, Any]] = []
    _stub_upstream(monkeypatch, sent)
    _, _, key = create_site_group_and_key()
    assert install_plugin(REWRITE_PLUGIN, "guard")["state"] == "active"

    response = _chat(client, key, "hello")
    assert response.status_code == 200, response.text
    assert sent[-1]["messages"] == [
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": "hello"},
    ]

    rejected = _chat(client, key, "say the forbidden phrase")
    assert rejected.status_code == 451, rejected.text
    assert rejected.json()["error"]["type"] == "plugin_rejected"
    assert rejected.json()["error"]["message"] == "Blocked by policy"
    assert len(sent) == 1


def test_request_observer_gets_one_record_per_request(
    client,
    admin_headers,
    monkeypatch,
    tmp_path: Path,
    install_plugin,
    create_site_group_and_key,
) -> None:
    sent: list[dict[str, Any]] = []
    _stub_upstream(monkeypatch, sent)
    _, _, key = create_site_group_and_key()
    install_plugin(OBSERVER_PLUGIN, "recorder")
    records_path = tmp_path / "records.jsonl"
    saved = client.put(
        "/api/admin/plugins/recorder/settings",
        headers=admin_headers,
        json={"values": {"path": str(records_path)}},
    )
    assert saved.status_code == 200, saved.text

    assert _chat(client, key, "hello").status_code == 200
    streamed = _chat(client, key, "hello", stream=True)
    assert streamed.status_code == 200, streamed.text

    deadline = time.monotonic() + 5
    lines: list[str] = []
    while time.monotonic() < deadline:
        if records_path.exists():
            lines = records_path.read_text(encoding="utf-8").splitlines()
            if len(lines) >= 2:
                break
        time.sleep(0.05)
    records = [json.loads(line) for line in lines]
    assert [(item["is_stream"], item["success"]) for item in records] == [
        (False, True),
        (True, True),
    ]
    assert all(item["lifecycle_status"] == "succeeded" for item in records)
    assert records[0]["gateway_key_id"] == key["id"]
    assert records[0]["attempt_count"] == 1
