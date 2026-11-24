from __future__ import annotations

import pytest
from pydantic import HttpUrl

from app.gateway.router.cooldown import ClaimDecision
from app.gateway.router.failover import RetryAction, next_candidate
from app.gateway.router.targets import RouteTarget, target_key
from app.models.channels import ChannelConfig
from app.models.protocols import ProtocolKind


@pytest.mark.parametrize("other_channel_available", [True, False])
def test_retry_channel_falls_back_to_eligible_same_channel_key(
    other_channel_available: bool,
) -> None:
    failed_channel = ChannelConfig(
        id="failed",
        name="Failed",
        protocol=ProtocolKind.OPENAI_CHAT,
        base_url=HttpUrl("https://failed.example.test"),
        api_key="fake-key",
    )
    other_channel = failed_channel.model_copy(update={"id": "other", "name": "Other"})
    failed_target = RouteTarget(
        channel=failed_channel, credential_id="first", model_name="model"
    )
    failed_channel_key = RouteTarget(
        channel=failed_channel, credential_id="second", model_name="model"
    )
    other_target = RouteTarget(
        channel=other_channel, credential_id="third", model_name="model"
    )

    result = next_candidate(
        [failed_target, failed_channel_key, other_target],
        failed=failed_target,
        tried={target_key(failed_target)},
        action=RetryAction.RETRY_CHANNEL,
        claim=lambda target: ClaimDecision(
            allowed=other_channel_available or target is failed_channel_key
        ),
    )

    assert result == (
        other_target if other_channel_available else failed_channel_key,
        False,
    )
