from __future__ import annotations

from conftest import assert_error, valid_site_payload
from lens_api.gateway.router import GatewayRouter, RouteSelection, RouteTarget
from lens_api.gateway.router.cooldown import ErrorCategory
from lens_api.models import (
    ChannelConfig,
    ProtocolKind,
    RoutingStrategy,
)
from lens_api.persistence.shared import SETTING_CORS_ALLOW_ORIGINS


def _routing_channel(
    channel_id: str,
    *,
    site_id: str = "",
) -> ChannelConfig:
    return ChannelConfig(
        id=channel_id,
        site_id=site_id,
        name=channel_id,
        protocol=ProtocolKind.OPENAI_CHAT,
        base_url=f"https://{channel_id}.example/v1",
        api_key="secret",
    )


def _select_targets(
    router: GatewayRouter,
    channels: list[ChannelConfig],
    strategy: RoutingStrategy,
) -> RouteSelection:
    return router.select(
        channels,
        ProtocolKind.OPENAI_CHAT,
        strategy=strategy,
        route_targets=[RouteTarget(channel=channel) for channel in channels],
        use_model_matching=False,
        cursor_key="routing-test",
    )


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


def test_failover_preserves_route_target_order() -> None:
    first_site_first = _routing_channel(
        "first-site-first",
        site_id="first-site",
    )
    second_site = _routing_channel(
        "second-site",
        site_id="second-site",
    )
    first_site_second = _routing_channel(
        "first-site-second",
        site_id="first-site",
    )

    selection = _select_targets(
        GatewayRouter(health_scoring_enabled=False),
        [first_site_first, second_site, first_site_second],
        RoutingStrategy.FAILOVER,
    )

    assert selection.primary.channel.id == "first-site-first"
    assert [target.channel.id for target in selection.fallbacks] == [
        "second-site",
        "first-site-second",
    ]


def test_failover_uses_next_model_group_target_while_first_is_cooling() -> None:
    first = _routing_channel("first", site_id="first-site")
    second_site = _routing_channel(
        "second-site",
        site_id="second-site",
    )
    same_site_fallback = _routing_channel(
        "same-site-fallback",
        site_id="first-site",
    )
    router = GatewayRouter(health_scoring_enabled=False)
    channels = [first, second_site, same_site_fallback]
    initial = _select_targets(router, channels, RoutingStrategy.FAILOVER)
    assert initial.primary.channel.id == "first"
    router.record_failure(first.id, "auth failed", category=ErrorCategory.AUTH)

    selection = _select_targets(router, channels, RoutingStrategy.FAILOVER)

    assert selection.primary.channel.id == "second-site"
    assert [target.channel.id for target in selection.fallbacks] == [
        "same-site-fallback"
    ]


def test_round_robin_preserves_route_target_order() -> None:
    first = _routing_channel("first")
    second = _routing_channel("second")
    router = GatewayRouter(health_scoring_enabled=False)

    selected = [
        _select_targets(
            router, [first, second], RoutingStrategy.ROUND_ROBIN
        ).primary.channel.id
        for _ in range(2)
    ]

    assert selected == ["first", "second"]


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
