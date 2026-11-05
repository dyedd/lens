from __future__ import annotations

import json
from email.parser import BytesParser
from email.policy import default

import httpx
import pytest
from conftest import gateway_headers, valid_site_payload


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("request_kind", ["generation", "json-edit", "multipart-edit"])
def test_proxy_images_forward_requests_responses_and_billing(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    request_kind,
    stream,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    create_site(
        valid_site_payload(protocols=["openai_image"], model_name="gpt-image-1")
    )
    create_model_group(
        name="public-image",
        items=[
            {
                "channel_id": "pc-1_openai_image",
                "credential_id": "cred-1",
                "model_name": "gpt-image-1",
                "enabled": True,
            }
        ],
    )
    price = client.put(
        "/api/admin/model-prices/public-image",
        headers=admin_headers,
        json={"model_key": "public-image", "image_price_per_image": 0.04},
    )
    assert price.status_code == 200, price.text
    path = (
        "/v1/images/generations" if request_kind == "generation" else "/v1/images/edits"
    )
    usage = {
        "input_tokens": 12,
        "input_tokens_details": {"image_tokens": 6, "text_tokens": 6},
        "output_tokens": 7,
        "total_tokens": 19,
    }
    payload = {"created": 123, "data": [{"b64_json": "YWJj"}], "usage": usage}
    event_kind = "image_generation" if request_kind == "generation" else "image_edit"
    frames = [
        {
            "type": f"{event_kind}.partial_image",
            "partial_image_index": 0,
            "b64_json": "eA==",
        },
        {"type": f"{event_kind}.completed", "b64_json": "YWJj", "usage": usage},
    ]
    sse = "".join(
        f"event: {frame['type']}\ndata: {json.dumps(frame)}\n\n" for frame in frames
    )
    sent = []

    async def send(_client, upstream, *, stream: bool, body_bytes: bytes):
        assert upstream.url == f"https://upstream.example{path}"
        assert upstream.headers["authorization"] == "Bearer upstream-secret"
        if request_kind == "multipart-edit":
            message = BytesParser(policy=default).parsebytes(
                f"Content-Type: {upstream.headers['content-type']}\r\n\r\n".encode()
                + body_bytes
            )
            fields = {}
            images = []
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if part.get_filename():
                    images.append(
                        (name, part.get_filename(), part.get_payload(decode=True))
                    )
                else:
                    fields[name] = part.get_content().strip()
            assert fields == {
                "model": "gpt-image-1",
                "prompt": "edit",
                "stream": str(stream).lower(),
            }
            assert images == [
                ("image[]", "first.png", b"first"),
                ("image[]", "second.png", b"second"),
            ]
        else:
            body = json.loads(body_bytes)
            assert body["model"] == "gpt-image-1"
            assert body["prompt"] == "edit"
            assert body["stream"] is stream
            if request_kind == "json-edit":
                assert body["images"] == [
                    {"image_url": "https://images.example/source.png"}
                ]
        sent.append(stream)
        return httpx.Response(
            200,
            content=sse if stream else json.dumps(payload),
            headers={
                "content-type": "text/event-stream" if stream else "application/json"
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    key = create_gateway_key()
    if request_kind == "multipart-edit":
        response = client.post(
            path,
            headers=gateway_headers(key),
            data={
                "model": "public-image",
                "prompt": "edit",
                "stream": str(stream).lower(),
            },
            files=[
                ("image[]", ("first.png", b"first", "image/png")),
                ("image[]", ("second.png", b"second", "image/png")),
            ],
        )
    else:
        body = {"model": "public-image", "prompt": "edit", "stream": stream}
        if request_kind == "json-edit":
            body["images"] = [{"image_url": "https://images.example/source.png"}]
        response = client.post(path, headers=gateway_headers(key), json=body)

    assert response.status_code == 200, response.text
    assert sent == [stream]
    if stream:
        assert response.text == sse
    else:
        assert response.json() == payload
    logs = client.get("/api/admin/request-logs/page", headers=admin_headers).json()[
        "items"
    ]
    assert logs[0]["success"] is True
    assert logs[0]["is_stream"] is stream
    assert (
        logs[0]["input_tokens"],
        logs[0]["image_input_tokens"],
        logs[0]["output_tokens"],
        logs[0]["total_tokens"],
    ) == (12, 6, 7, 19)
    assert logs[0]["billing_units"] == 1
    assert logs[0]["total_cost_usd"] == pytest.approx(0.04)
