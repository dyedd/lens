from __future__ import annotations

from lens_api.gateway.service.proxy_routes import _build_gemini_models_payload
from lens_api.models import (
    GatewayApiKey,
    ModelGroup,
    ModelGroupItem,
    ProtocolKind,
    RoutingStrategy,
)


def _gateway_key() -> GatewayApiKey:
    return GatewayApiKey(
        id="key-1",
        api_key="sk-test",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )


def test_gemini_model_list_requires_enabled_reachable_route_item() -> None:
    execution_group = ModelGroup(
        id="exec",
        name="real-model",
        protocols=[ProtocolKind.OPENAI_CHAT, ProtocolKind.GEMINI],
        strategy=RoutingStrategy.ROUND_ROBIN,
        items=[
            ModelGroupItem(
                channel_id="channel-openai",
                protocol=ProtocolKind.OPENAI_CHAT,
                credential_id="cred-1",
                model_name="real-model",
                enabled=True,
            ),
            ModelGroupItem(
                channel_id="channel-gemini",
                protocol=ProtocolKind.GEMINI,
                credential_id="cred-1",
                model_name="real-model",
                enabled=False,
            ),
        ],
    )
    route_group = ModelGroup(
        id="route",
        name="alias-model",
        protocols=[ProtocolKind.GEMINI],
        strategy=RoutingStrategy.ROUND_ROBIN,
        route_group_id=execution_group.id,
    )

    payload = _build_gemini_models_payload(
        [execution_group, route_group],
        _gateway_key(),
    )

    assert payload["models"] == []
