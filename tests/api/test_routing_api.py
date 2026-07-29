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
    priority: int,
) -> ChannelConfig:
    return ChannelConfig(
        id=channel_id,
        name=channel_id,
        priority=priority,
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
        cursor_key="priority-test",
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


def test_failover_prefers_channel_priority_then_preserves_group_order() -> None:
    low = _routing_channel("low", priority=0)
    high_first = _routing_channel("high-first", priority=10)
    high_second = _routing_channel("high-second", priority=10)

    selection = _select_targets(
        GatewayRouter(health_scoring_enabled=False),
        [low, high_first, high_second],
        RoutingStrategy.FAILOVER,
    )

    assert selection.primary.channel.id == "high-first"
    assert [target.channel.id for target in selection.fallbacks] == [
        "high-second",
        "low",
    ]


def test_failover_uses_lower_priority_while_higher_priority_is_cooling() -> None:
    high = _routing_channel("high", priority=10)
    low = _routing_channel("low", priority=0)
    router = GatewayRouter(health_scoring_enabled=False)
    initial = _select_targets(router, [low, high], RoutingStrategy.FAILOVER)
    assert initial.primary.channel.id == "high"
    router.record_failure(high.id, "auth failed", category=ErrorCategory.AUTH)

    selection = _select_targets(router, [low, high], RoutingStrategy.FAILOVER)

    assert selection.primary.channel.id == "low"
    assert selection.fallbacks == []


def test_round_robin_ignores_channel_priority() -> None:
    low = _routing_channel("low", priority=0)
    high = _routing_channel("high", priority=10)
    router = GatewayRouter(health_scoring_enabled=False)

    selected = [
        _select_targets(
            router, [low, high], RoutingStrategy.ROUND_ROBIN
        ).primary.channel.id
        for _ in range(2)
    ]

    assert selected == ["low", "high"]


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
