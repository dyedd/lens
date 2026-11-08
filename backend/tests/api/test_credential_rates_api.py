from __future__ import annotations

import httpx
import pytest
from conftest import valid_site_payload


@pytest.mark.parametrize("source", ["sub2api", "newapi"])
def test_credential_rate_sync_persists_observed_multiplier(
    client, peer_client, admin_headers, create_site, monkeypatch, source
) -> None:
    payload = valid_site_payload()
    payload["credentials"][0].update(
        rate_source=source,
        rate_protocol_config_id="pc-1",
        rate_group="standard" if source == "newapi" else "",
    )
    site = create_site(payload)
    groups = peer_client.get("/api/admin/model-groups", headers=admin_headers)
    assert groups.status_code == 200, groups.text
    assert groups.json()[0]["items"][0]["rate_multiplier"] is None

    async def send(_client, request, **_kwargs):
        if source == "sub2api":
            assert request.url.path == "/v1/sub2api/billing"
            assert request.headers["authorization"] == "Bearer upstream-secret"
            body = {
                "object": "sub2api.key_billing",
                "schema_version": 1,
                "billing_scope": "token",
                "peak_rate_enabled": False,
                "group_rate_multiplier": 1,
                "user_rate_multiplier": None,
                "resolved_rate_multiplier": 1.5,
                "effective_rate_multiplier": 1.5,
                "observed_at": "2026-11-07T00:00:00Z",
            }
        else:
            assert request.url.path == "/api/pricing"
            body = {"success": True, "group_ratio": {"standard": 1.5}}
        return httpx.Response(200, json=body, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    response = client.post(
        f"/api/admin/sites/{site['id']}/credentials/cred-1/rate-sync",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    credential = response.json()
    assert credential["rate_multiplier"] == 1.5
    assert credential["rate_observed_at"]
    assert credential["rate_last_synced_at"]
    assert credential["rate_last_error"] == ""
    persisted = client.get("/api/admin/sites", headers=admin_headers)
    assert persisted.status_code == 200
    saved = next(item for item in persisted.json() if item["id"] == site["id"])
    assert saved["credentials"][0]["rate_multiplier"] == 1.5
    groups = peer_client.get("/api/admin/model-groups", headers=admin_headers)
    assert groups.status_code == 200, groups.text
    assert groups.json()[0]["items"][0]["rate_multiplier"] == 1.5
