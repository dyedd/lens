from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from conftest import gateway_headers, json_response
from lens_api.models import ProtocolKind


def test_proxy_image_edits_forwards_form_fields_and_files(
    client,
    monkeypatch,
    create_gateway_key,
) -> None:
    key = create_gateway_key()
    calls: list[dict[str, Any]] = []

    async def fake_proxy(
        protocol: ProtocolKind,
        body: dict[str, Any],
        _gateway_key: Any,
        _user_agent: str | None,
        _forwarded_headers: dict[str, str] | None = None,
        *,
        path_suffix: str = "",
        multipart_files: list[Any] | None = None,
    ) -> JSONResponse:
        calls.append(
            {
                "protocol": protocol.value,
                "body": body,
                "path_suffix": path_suffix,
                "files": [
                    {
                        "field": field,
                        "filename": file_info[0],
                        "size": len(file_info[1]),
                        "content_type": file_info[2],
                    }
                    for field, file_info in (multipart_files or [])
                ],
            }
        )
        return json_response({"ok": True})

    import lens_api.gateway.service.proxy_routes as proxy_routes

    monkeypatch.setattr(proxy_routes, "_proxy_protocol", fake_proxy)

    response = client.post(
        "/v1/images/edits",
        headers=gateway_headers(key),
        data={"model": "gpt-image-1", "prompt": "edit"},
        files={"image": ("image.png", b"abc", "image/png")},
    )

    assert response.status_code == 200
    assert calls[0]["protocol"] == "openai_image"
    assert calls[0]["body"] == {"model": "gpt-image-1", "prompt": "edit"}
    assert calls[0]["path_suffix"] == "images/edits"
    assert calls[0]["files"] == [
        {
            "field": "image",
            "filename": "image.png",
            "size": 3,
            "content_type": "image/png",
        }
    ]


def test_proxy_rejects_non_object_json_body(client, create_gateway_key) -> None:
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json=["not", "an", "object"],
    )

    assert response.status_code == 400
    assert response.json()["error"]["message"] == (
        "Chat completion request body must be a JSON object"
    )


def test_proxy_rejects_malformed_json_body(client, create_gateway_key) -> None:
    key = create_gateway_key()

    response = client.post(
        "/v1/chat/completions",
        headers={**gateway_headers(key), "content-type": "application/json"},
        content="{",
    )

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Invalid JSON payload"
