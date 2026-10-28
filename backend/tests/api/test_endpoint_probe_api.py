from __future__ import annotations

import httpx
from conftest import run_async


def test_endpoint_probe_times_the_address(
    client, admin_headers, app_state, monkeypatch
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "HEAD"
        assert request.url.path == "/v1"
        return httpx.Response(404, request=request)

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    import app.gateway.service.tasks.endpoint_probe as endpoint_probe

    monkeypatch.setattr(endpoint_probe, "app_state", app_state)
    monkeypatch.setattr(
        endpoint_probe, "resolve_http_client", lambda _proxy: upstream_client
    )
    try:
        response = client.post(
            "/api/admin/endpoint-probes",
            headers=admin_headers,
            json={"base_url": "https://upstream.example/v1"},
        )
    finally:
        run_async(upstream_client.aclose())

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["success"] is True
    assert result["status_code"] == 404
    assert result["latency_ms"] >= 0
    assert result["error_message"] == ""
