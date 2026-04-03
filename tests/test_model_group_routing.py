from __future__ import annotations

from lens.gateway.router import RoundRobinRouter, RouteTarget
from lens.models import ProtocolKind, ProviderConfig, ProviderStatus, RoutingStrategy


def _provider(provider_id: str, name: str, models: list[str]) -> ProviderConfig:
    return ProviderConfig(
        id=provider_id,
        name=name,
        protocol=ProtocolKind.OPENAI_CHAT,
        base_url="https://example.com",
        api_key="sk-test",
        status=ProviderStatus.ENABLED,
        model_patterns=models,
        headers={},
        keys=[],
        proxy=False,
        channel_proxy="",
        param_override="",
        match_regex="",
    )


def test_route_targets_follow_round_robin_order():
    router = RoundRobinRouter()
    provider_a = _provider("openai-1", "OpenAI A", ["gpt-4.1"])
    provider_b = _provider("openai-2", "OpenAI B", ["gpt-4.1"])
    targets = [
        RouteTarget(provider=provider_a, model_name="gpt-4.1"),
        RouteTarget(provider=provider_b, model_name="gpt-4.1-mini"),
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

    assert first.primary.provider.id == "openai-1"
    assert first.primary.model_name == "gpt-4.1"
    assert second.primary.provider.id == "openai-2"
    assert second.primary.model_name == "gpt-4.1-mini"


def test_preview_returns_ordered_items():
    router = RoundRobinRouter()
    provider_a = _provider("openai-1", "OpenAI A", ["gpt-4.1"])
    provider_b = _provider("openai-2", "OpenAI B", ["gpt-4.1"])
    preview = router.preview(
        [provider_a, provider_b],
        ProtocolKind.OPENAI_CHAT,
        "group-model",
        strategy=RoutingStrategy.FAILOVER,
        route_targets=[
            RouteTarget(provider=provider_a, model_name="gpt-4.1"),
            RouteTarget(provider=provider_b, model_name="gpt-4.1-mini"),
        ],
        use_model_matching=False,
        matched_group_name="group-model",
    )

    assert preview.matched_provider_ids == ["openai-1", "openai-2"]
    assert [item.model_name for item in preview.items] == ["gpt-4.1", "gpt-4.1-mini"]


def test_failover_always_starts_from_first_target():
    router = RoundRobinRouter()
    provider_a = _provider("openai-1", "OpenAI A", ["gpt-4.1"])
    provider_b = _provider("openai-2", "OpenAI B", ["gpt-4.1"])
    targets = [
        RouteTarget(provider=provider_a, model_name="gpt-4.1"),
        RouteTarget(provider=provider_b, model_name="gpt-4.1-mini"),
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

    assert first.primary.provider.id == "openai-1"
    assert second.primary.provider.id == "openai-1"
    assert [target.provider.id for target in first.fallbacks] == ["openai-2"]
