from typing import Any

import httpx
from conftest import gateway_headers, valid_site_payload

from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.protocols import ProtocolKind

_SSE_RETRY_BODY = (
    b'event: message_start\ndata: {"type":"message_start",'
    b'"message":{"id":"msg_retry","type":"message",'
    b'"role":"assistant","model":"claude-upstream",'
    b'"content":[],"stop_reason":null,"stop_sequence":null,'
    b'"usage":{"input_tokens":1,"output_tokens":0}}}\n\n'
    b'event: message_stop\ndata: {"type":"message_stop"}\n\n'
)


def _claude_group(create_site, create_model_group) -> None:
    create_site(
        valid_site_payload(
            protocols=[ProtocolKind.ANTHROPIC.value],
            model_name="claude-upstream",
        )
    )
    create_model_group(
        name="claude-group",
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.ANTHROPIC
                ),
                "credential_id": "cred-1",
                "model_name": "claude-upstream",
                "enabled": True,
            }
        ],
    )


def test_stream_html_response_fails_without_retry(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    _claude_group(create_site, create_model_group)
    sends = 0

    async def fake_send_upstream(
        _upstream_client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        nonlocal sends
        sends += 1
        assert stream
        return httpx.Response(
            200,
            content=b"<html><body>temporary upstream page</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(key),
        json={
            "model": "claude-group",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 16,
            "stream": True,
        },
    )

    assert sends == 1
    assert response.status_code == 502, response.text
    message = response.json()["error"]["message"]
    assert "Invalid upstream response body" in message
    assert "<html>" not in message


def test_stream_html_labelled_sse_body_is_accepted(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    _claude_group(create_site, create_model_group)
    sends = 0

    async def fake_send_upstream(
        _upstream_client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        nonlocal sends
        sends += 1
        assert stream
        return httpx.Response(
            200,
            content=_SSE_RETRY_BODY,
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(key),
        json={
            "model": "claude-group",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 16,
            "stream": True,
        },
    )

    assert sends == 1
    assert response.status_code == 200, response.text
    assert '"id":"msg_retry"' in response.text
