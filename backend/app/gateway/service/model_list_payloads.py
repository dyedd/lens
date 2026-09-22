from __future__ import annotations

from typing import Any

from ...models.gateway_keys import GatewayApiKey
from ...models.model_groups import ModelGroupItemState, ModelGroupView
from ...models.protocols import ProtocolKind
from ..converters import can_reach_protocol
from .auth import gateway_key_allows_model

OPENAI_LIST_PROTOCOLS: frozenset[ProtocolKind] = frozenset(
    {
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
        ProtocolKind.OPENAI_EMBEDDING,
        ProtocolKind.OPENAI_IMAGE,
        ProtocolKind.RERANK,
    }
)

ALL_MODEL_LIST_PROTOCOLS: frozenset[ProtocolKind] = frozenset(
    protocol for protocol in ProtocolKind if protocol != ProtocolKind.AUTO
)


def build_openai_models_payload(
    groups: list[ModelGroupView],
    gateway_key: GatewayApiKey,
    protocols: frozenset[ProtocolKind] | set[ProtocolKind] = OPENAI_LIST_PROTOCOLS,
) -> dict[str, Any]:
    """Build an OpenAI-compatible model list from visible groups."""
    names = _filtered_group_names(groups, gateway_key, protocols)
    return {
        "object": "list",
        "data": [
            {
                "id": name,
                "object": "model",
                "created": 0,
                "owned_by": "lens",
            }
            for name in names
        ],
    }


def build_gemini_models_payload(
    groups: list[ModelGroupView], gateway_key: GatewayApiKey
) -> dict[str, Any]:
    """Build a Gemini-compatible model list from visible groups."""
    names = _filtered_group_names(groups, gateway_key, {ProtocolKind.GEMINI})
    return {
        "models": [
            {
                "name": f"models/{name}",
                "baseModelId": name,
                "version": "001",
                "displayName": name,
                "supportedGenerationMethods": [
                    "generateContent",
                    "streamGenerateContent",
                ],
            }
            for name in names
        ]
    }


def _filtered_group_names(
    groups: list[ModelGroupView],
    gateway_key: GatewayApiKey,
    protocols: frozenset[ProtocolKind] | set[ProtocolKind],
) -> list[str]:
    group_by_id = {group.id: group for group in groups}
    requested_protocols = frozenset(protocols)

    def has_ready_item(group: ModelGroupView) -> bool:
        target = (
            group_by_id.get(group.route_group_id) if group.route_group_id else group
        )
        return bool(
            target
            and any(
                item.state == ModelGroupItemState.READY
                and item.protocol is not None
                and any(
                    can_reach_protocol(item.protocol, protocol)
                    for protocol in requested_protocols
                )
                for item in target.items
            )
        )

    return sorted(
        {
            group.name.strip()
            for group in groups
            if group.name.strip()
            and set(group.client_protocols) & requested_protocols
            and has_ready_item(group)
            and gateway_key_allows_model(gateway_key, group.name)
        }
    )
