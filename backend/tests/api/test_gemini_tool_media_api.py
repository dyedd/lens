from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from conftest import gateway_headers, valid_site_payload

_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j0XkAAAAASUVORK5CYII="
_FILE_URL = "https://files.example/report.pdf"


@pytest.mark.parametrize("source", ["anthropic", "gemini"])
@pytest.mark.parametrize("media", ["image", "file"])
def test_gemini_tool_result_media_survives_protocol_conversion(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    source,
    media,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    target = "gemini" if source == "anthropic" else "anthropic"
    model = "gemini-2.5-flash" if target == "gemini" else "claude-sonnet-4"
    create_site(valid_site_payload(protocols=[target], model_name=model))
    create_model_group(
        name="public-media",
        items=[
            {
                "channel_id": f"pc-1_{target}",
                "credential_id": "cred-1",
                "model_name": model,
            }
        ],
    )
    anthropic_media: dict[str, Any] = (
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": _IMAGE,
            },
        }
        if media == "image"
        else {"type": "document", "source": {"type": "url", "url": _FILE_URL}}
    )
    gemini_media = (
        {"inlineData": {"mimeType": "image/png", "data": _IMAGE}}
        if media == "image"
        else {"fileData": {"mimeType": "application/pdf", "fileUri": _FILE_URL}}
    )
    sent: list[dict[str, Any]] = []

    async def send(_client, upstream, *, stream, body_bytes):
        sent.append(json.loads(body_bytes))
        payload = (
            {
                "modelVersion": model,
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "Inspected"}]},
                        "finishReason": "STOP",
                    }
                ],
            }
            if target == "gemini"
            else {
                "id": "msg-media",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [{"type": "text", "text": "Inspected"}],
                "stop_reason": "end_turn",
            }
        )
        return httpx.Response(
            200, json=payload, request=httpx.Request("POST", upstream.url)
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    key = create_gateway_key()
    if source == "anthropic":
        path = "/v1/messages"
        headers = gateway_headers(key)
        body = {
            "model": "public-media",
            "max_tokens": 64,
            "messages": [
                {"role": "user", "content": "Inspect the tool output."},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call-1",
                            "name": "inspect",
                            "input": {},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call-1",
                            "content": [anthropic_media],
                        }
                    ],
                },
            ],
        }
    else:
        path = "/v1beta/models/public-media:generateContent"
        headers = {"x-goog-api-key": key["api_key"]}
        body = {
            "contents": [
                {"role": "user", "parts": [{"text": "Inspect the tool output."}]},
                {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "id": "call-1",
                                "name": "inspect",
                                "args": {},
                            }
                        }
                    ],
                },
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                "id": "call-1",
                                "name": "inspect",
                                "response": {"result": "file returned"},
                                "parts": [gemini_media],
                            }
                        }
                    ],
                },
            ]
        }
    response = client.post(path, headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert "Inspected" in response.text
    assert len(sent) == 1
    if target == "gemini":
        parts = sent[0]["contents"][-1]["parts"]
        assert parts[0]["functionResponse"]["name"] == "inspect"
        assert parts[1:] == [gemini_media]
    else:
        result = next(
            part
            for message in sent[0]["messages"]
            if isinstance(message["content"], list)
            for part in message["content"]
            if part["type"] == "tool_result"
        )
        assert result["tool_use_id"] == "call-1"
        assert isinstance(result["content"], list)
        assert anthropic_media in result["content"]
