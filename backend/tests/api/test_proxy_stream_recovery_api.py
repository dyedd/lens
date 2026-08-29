from typing import Any

import httpx
import pytest
from conftest import gateway_headers, valid_site_payload

from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.protocols import ProtocolKind


@pytest.mark.parametrize("retry_succeeds", [True, False])
def test_stream_html_response_retries_once_with_fresh_connection(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
    retry_succeeds: bool,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

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
    clients: list[httpx.AsyncClient] = []

    async def fake_send_upstream(
        upstream_client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert stream
        clients.append(upstream_client)
        if len(clients) == 1 or not retry_succeeds:
            content = b"<html><body>temporary upstream page</body></html>"
            content_type = "text/html; charset=utf-8"
        else:
            content = (
                b'event: message_start\ndata: {"type":"message_start",'
                b'"message":{"id":"msg_retry","type":"message",'
                b'"role":"assistant","model":"claude-upstream",'
                b'"content":[],"stop_reason":null,"stop_sequence":null,'
                b'"usage":{"input_tokens":1,"output_tokens":0}}}\n\n'
                b'event: message_stop\ndata: {"type":"message_stop"}\n\n'
            )
            content_type = "text/event-stream"
        return httpx.Response(
            200,
            content=content,
            headers={"content-type": content_type},
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

    assert len(clients) == 2
    assert clients[0] is not clients[1]
    if retry_succeeds:
        assert response.status_code == 200, response.text
        assert '"id":"msg_retry"' in response.text
    else:
        assert response.status_code == 502, response.text
        assert "Invalid upstream response body" in response.json()["error"]["message"]
