import pytest

from lens_api.gateway.router import RoundRobinRouter, RouteTarget
from lens_api.models import ChannelConfig, ChannelKeyItem, ChannelStatus, ProtocolKind


def _channel(
    channel_id: str,
    protocol: ProtocolKind,
    *,
    status: ChannelStatus = ChannelStatus.ENABLED,
    keys: list[ChannelKeyItem] | None = None,
) -> ChannelConfig:
    return ChannelConfig(
        id=channel_id,
        name=channel_id,
        protocol=protocol,
        base_url="https://api.example.com",
        api_key="sk-test",
        status=status,
        keys=keys or [],
    )


def test_route_targets_are_filtered_with_can_reach_protocol() -> None:
    router = RoundRobinRouter()
    chat = _channel("chat", ProtocolKind.OPENAI_CHAT)
    embedding = _channel("embedding", ProtocolKind.OPENAI_EMBEDDING)

    selection = router.select(
        [],
        ProtocolKind.ANTHROPIC,
        route_targets=[
            RouteTarget(channel=embedding, model_name="text-embedding-3-large"),
            RouteTarget(channel=chat, model_name="gpt-5-mini"),
        ],
    )

    assert selection.primary.channel.id == "chat"
    assert selection.fallbacks == []


def test_direct_channel_pool_still_requires_exact_protocol() -> None:
    router = RoundRobinRouter()

    with pytest.raises(
        LookupError,
        match="No enabled channels available for protocol=anthropic",
    ):
        router.select(
            [_channel("chat", ProtocolKind.OPENAI_CHAT)],
            ProtocolKind.ANTHROPIC,
        )


def test_router_raises_when_all_route_targets_incompatible() -> None:
    router = RoundRobinRouter()

    with pytest.raises(LookupError, match="No enabled channels matched claude-3"):
        router.select(
            [],
            ProtocolKind.ANTHROPIC,
            requested_model="claude-3",
            route_targets=[
                RouteTarget(
                    channel=_channel("embedding", ProtocolKind.OPENAI_EMBEDDING),
                    model_name="text-embedding-3-large",
                )
            ],
        )


def test_route_target_with_disabled_credential_is_skipped() -> None:
    router = RoundRobinRouter()
    channel = _channel(
        "chat",
        ProtocolKind.OPENAI_CHAT,
        keys=[
            ChannelKeyItem(id="disabled-key", key="sk-disabled", enabled=False),
            ChannelKeyItem(id="enabled-key", key="sk-enabled", enabled=True),
        ],
    )

    selection = router.select(
        [],
        ProtocolKind.OPENAI_CHAT,
        route_targets=[
            RouteTarget(
                channel=channel,
                model_name="gpt-5-mini",
                credential_id="disabled-key",
            ),
            RouteTarget(
                channel=channel,
                model_name="gpt-5-mini",
                credential_id="enabled-key",
            ),
        ],
    )

    assert selection.primary.credential_id == "enabled-key"
    assert selection.fallbacks == []
