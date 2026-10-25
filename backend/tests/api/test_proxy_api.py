from __future__ import annotations

from typing import Any

from conftest import gateway_headers, json_response

from app.models.protocols import ProtocolKind


def test_proxy_routes_accept_supported_request_shapes(
    client,
    monkeypatch,
    create_gateway_key,
) -> None:
    key = create_gateway_key()
    calls: list[dict[str, Any]] = []

    async def fake_proxy(
        protocol: ProtocolKind,
        body: dict[str, Any],
        gateway_key: Any,
        user_agent: str | None,
        forwarded_headers: dict[str, str] | None = None,
        *,
        path_suffix: str = "",
        multipart_files: list[Any] | None = None,
    ):
        calls.append(
            {
                "protocol": protocol.value,
                "body": body,
                "gateway_key_id": gateway_key.id,
                "user_agent": user_agent,
                "path_suffix": path_suffix,
                "multipart_files": multipart_files or [],
            }
        )
        return json_response({"ok": True, "protocol": protocol.value})

    import app.gateway.service.proxy_routes as proxy_routes

    monkeypatch.setattr(proxy_routes, "proxy_protocol", fake_proxy)
    headers = {**gateway_headers(key), "User-Agent": "lens-tests"}
    cases = [
        ("/v1/chat/completions", {"model": "gpt-4o"}, "openai_chat"),
        ("/v1/responses", {"model": "gpt-4o", "input": "hello"}, "openai_responses"),
        ("/v1/embeddings", {"model": "text-embedding-3-small"}, "openai_embedding"),
        (
            "/v1/images/generations",
            {"model": "gpt-image-1", "prompt": "test"},
            "openai_image",
        ),
        ("/v1/rerank", {"model": "reranker"}, "rerank"),
        ("/v1/messages", {"model": "claude-3", "messages": []}, "anthropic"),
        (
            "/v1beta/interactions",
            {"model": "gemini-2.5-flash", "input": "hello"},
            "gemini",
        ),
    ]

    for path, body, expected_protocol in cases:
        response = client.post(path, headers=headers, json=body)

        assert response.status_code == 200, response.text
        assert response.json()["protocol"] == expected_protocol
        assert calls[-1]["body"] == body
        assert calls[-1]["gateway_key_id"] == key["id"]
        assert calls[-1]["user_agent"] == "lens-tests"
