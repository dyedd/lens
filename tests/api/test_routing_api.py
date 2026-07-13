from __future__ import annotations

from conftest import assert_error, valid_site_payload
from lens_api.persistence.shared import SETTING_CORS_ALLOW_ORIGINS


def test_router_snapshot_requires_admin(client) -> None:
    response = client.get("/api/admin/routes")

    assert_error(response, 401, "Not authenticated")


def test_router_snapshot_is_empty_without_channels(client, admin_headers) -> None:
    response = client.get("/api/admin/routes", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["health"] == []
    assert payload["routes"]
    assert all(route["channel_ids"] == [] for route in payload["routes"])
    assert all(route["next_channel_id"] is None for route in payload["routes"])


def test_router_snapshot_returns_route_and_health_state(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload())

    response = client.get("/api/admin/routes", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert "routes" in payload
    assert "health" in payload


def test_cors_preflight_allows_any_origin_by_default(client) -> None:
    response = client.options(
        "/anything",
        headers={
            "Origin": "https://app.example",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-headers"] == "authorization"


def test_cors_preflight_respects_configured_origins(client, admin_headers) -> None:
    settings_response = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {
                    "key": SETTING_CORS_ALLOW_ORIGINS,
                    "value": "https://allowed.example",
                }
            ]
        },
    )
    assert settings_response.status_code == 200

    allowed = client.options(
        "/anything",
        headers={"Origin": "https://allowed.example"},
    )
    blocked = client.options(
        "/anything",
        headers={"Origin": "https://blocked.example"},
    )

    assert allowed.status_code == 204
    assert allowed.headers["access-control-allow-origin"] == "https://allowed.example"
    assert allowed.headers["vary"] == "Origin"
    assert "access-control-allow-origin" not in blocked.headers
