from time import monotonic

from pydantic import HttpUrl

from app.core.cooldown_rules import ErrorCategory
from app.gateway.router.cooldown import CooldownPolicy
from app.gateway.router.health import HealthTracker
from app.gateway.router.targets import RouteTarget
from app.models.channels import ChannelConfig, ChannelDiscoveredModel, ChannelKeyItem
from app.models.protocols import ProtocolKind


def test_reconciling_removed_model_preserves_same_id_credential_cooldown() -> None:
    channel = ChannelConfig(
        id="channel",
        name="Channel",
        protocol=ProtocolKind.OPENAI_CHAT,
        base_url=HttpUrl("https://channel.example.test"),
        api_key="fake-key",
        keys=[ChannelKeyItem(id="same", key="fake-credential")],
        models=[
            ChannelDiscoveredModel(credential_id="same", model_name="same"),
            ChannelDiscoveredModel(credential_id="same", model_name="remaining"),
        ],
    )
    tracker = HealthTracker(
        health_scoring_enabled=True,
        health_window_seconds=60,
        health_penalty_weight=1,
        health_min_samples=1,
        cooldown_policy=CooldownPolicy(failure_threshold=1),
    )
    tracker.reconcile_channels([channel])
    tracker.record_failure(
        channel.id,
        "Credential rejected",
        category=ErrorCategory.AUTH,
        credential_id="same",
        model_name="same",
        fault_protocol="",
        scope="key",
        cooldown_seconds=60,
    )
    tracker.record_failure(
        channel.id,
        "Model unavailable",
        category=ErrorCategory.SERVER,
        credential_id="same",
        model_name="same",
        fault_protocol="",
        scope="model",
        cooldown_seconds=60,
    )

    updated_channel = channel.model_copy(update={"models": [channel.models[1]]})
    tracker.reconcile_channels([updated_channel])
    target = RouteTarget(
        channel=updated_channel,
        credential_id="same",
        model_name="remaining",
    )

    assert tracker.cooldown_remaining_seconds(target, now=monotonic()) > 0
