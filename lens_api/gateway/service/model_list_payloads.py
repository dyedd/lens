from __future__ import annotations

from typing import Any

from ...models import GatewayApiKey, ModelGroup, ProtocolKind
from ..converters import can_reach_protocol
from .auth import _gateway_key_allows_model

OPENAI_LIST_PROTOCOLS: frozenset[ProtocolKind] = frozenset(
    {
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
        ProtocolKind.OPENAI_EMBEDDING,
        ProtocolKind.OPENAI_IMAGE,
        ProtocolKind.RERANK,
    }
)

ALL_MODEL_LIST_PROTOCOLS: frozenset[ProtocolKind] = frozenset(ProtocolKind)


def build_openai_models_payload(
    groups: list[ModelGroup],
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


def build_anthropic_models_payload(
    groups: list[ModelGroup], gateway_key: GatewayApiKey
) -> dict[str, Any]:
    """Build an Anthropic-compatible model list from visible groups."""
    names = _filtered_group_names(
        groups, gateway_key, frozenset({ProtocolKind.ANTHROPIC})
    )
    return {
        "data": [
            {
                "id": name,
                "type": "model",
                "display_name": name,
                "created_at": "1970-01-01T00:00:00Z",
            }
            for name in names
        ],
        "first_id": names[0] if names else None,
        "last_id": names[-1] if names else None,
        "has_more": False,
    }


def build_gemini_models_payload(
    groups: list[ModelGroup], gateway_key: GatewayApiKey
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
    groups: list[ModelGroup],
    gateway_key: GatewayApiKey,
    protocols: frozenset[ProtocolKind] | set[ProtocolKind],
) -> list[str]:
    group_by_id = {group.id: group for group in groups}
    requested_protocols = frozenset(protocols)

    def has_enabled_item(group: ModelGroup) -> bool:
        target = (
            group_by_id.get(group.route_group_id) if group.route_group_id else group
        )
        return bool(
            target
            and any(
                item.enabled
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
            and set(group.protocols) & requested_protocols
            and has_enabled_item(group)
            and _gateway_key_allows_model(gateway_key, group.name)
        }
    )
