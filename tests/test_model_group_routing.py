from __future__ import annotations

from lens.gateway.router import RoundRobinRouter, RouteTarget
from lens.models import ChannelConfig, ChannelStatus, ProtocolKind, RoutingStrategy


def _channel(channel_id: str, name: str, models: list[str]) -> ChannelConfig:
    return ChannelConfig(
        id=channel_id,
        name=name,
        protocol=ProtocolKind.OPENAI_CHAT,
        base_url="https://example.com",
        api_key="sk-test",
        status=ChannelStatus.ENABLED,
        model_patterns=models,
        headers={},
        keys=[],
        channel_proxy="",
        param_override="",
        match_regex="",
    )


def test_route_targets_follow_round_robin_order():
    router = RoundRobinRouter()
    provider_a = _channel("openai-1", "OpenAI A", ["gpt-4.1"])
    provider_b = _channel("openai-2", "OpenAI B", ["gpt-4.1"])
    targets = [
        RouteTarget(channel=provider_a, model_name="gpt-4.1"),
        RouteTarget(channel=provider_b, model_name="gpt-4.1-mini"),
    ]

    first = router.select(
        [provider_a, provider_b],
        ProtocolKind.OPENAI_CHAT,
        "group-model",
        strategy=RoutingStrategy.ROUND_ROBIN,
        route_targets=targets,
        use_model_matching=False,
        cursor_key="openai_chat:group-1",
    )
    second = router.select(
        [provider_a, provider_b],
        ProtocolKind.OPENAI_CHAT,
        "group-model",
        strategy=RoutingStrategy.ROUND_ROBIN,
        route_targets=targets,
        use_model_matching=False,
        cursor_key="openai_chat:group-1",
    )

    assert first.primary.channel.id == "openai-1"
    assert first.primary.model_name == "gpt-4.1"
    assert second.primary.channel.id == "openai-2"
    assert second.primary.model_name == "gpt-4.1-mini"


def test_preview_returns_ordered_items():
    router = RoundRobinRouter()
    provider_a = _channel("openai-1", "OpenAI A", ["gpt-4.1"])
    provider_b = _channel("openai-2", "OpenAI B", ["gpt-4.1"])
    preview = router.preview(
        [provider_a, provider_b],
        ProtocolKind.OPENAI_CHAT,
        "group-model",
        strategy=RoutingStrategy.FAILOVER,
        route_targets=[
            RouteTarget(channel=provider_a, model_name="gpt-4.1"),
            RouteTarget(channel=provider_b, model_name="gpt-4.1-mini"),
        ],
        use_model_matching=False,
        matched_group_name="group-model",
    )

    assert preview.matched_channel_ids == ["openai-1", "openai-2"]
    assert [item.model_name for item in preview.items] == ["gpt-4.1", "gpt-4.1-mini"]


def test_failover_always_starts_from_first_target():
    router = RoundRobinRouter()
    provider_a = _channel("openai-1", "OpenAI A", ["gpt-4.1"])
    provider_b = _channel("openai-2", "OpenAI B", ["gpt-4.1"])
    targets = [
        RouteTarget(channel=provider_a, model_name="gpt-4.1"),
        RouteTarget(channel=provider_b, model_name="gpt-4.1-mini"),
    ]

    first = router.select(
        [provider_a, provider_b],
        ProtocolKind.OPENAI_CHAT,
        "group-model",
        strategy=RoutingStrategy.FAILOVER,
        route_targets=targets,
        use_model_matching=False,
        cursor_key="openai_chat:group-1",
    )
    second = router.select(
        [provider_a, provider_b],
        ProtocolKind.OPENAI_CHAT,
        "group-model",
        strategy=RoutingStrategy.FAILOVER,
        route_targets=targets,
        use_model_matching=False,
        cursor_key="openai_chat:group-1",
    )

    assert first.primary.channel.id == "openai-1"
    assert second.primary.channel.id == "openai-1"
    assert [target.channel.id for target in first.fallbacks] == ["openai-2"]

