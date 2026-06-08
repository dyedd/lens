from __future__ import annotations

from .runtime_context import (
    Any,
    Depends,
    GatewayApiKey,
    HTTPException,
    ModelGroup,
    ProtocolKind,
    Request,
    Response,
    app_state,
    can_reach_protocol,
)
from .auth import _gateway_key_allows_model
from .upstream_http import _forward_anthropic_headers
from .proxy_flow import _proxy_protocol
from .auth import get_current_gateway_key


async def proxy_openai_chat(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
) -> Response:
    body = await request.json()
    return await _proxy_protocol(
        ProtocolKind.OPENAI_CHAT,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


async def proxy_openai_responses(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
) -> Response:
    body = await request.json()
    return await _proxy_protocol(
        ProtocolKind.OPENAI_RESPONSES,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


async def proxy_anthropic_messages(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
) -> Response:
    body = await request.json()
    return await _proxy_protocol(
        ProtocolKind.ANTHROPIC,
        body,
        gateway_key,
        request.headers.get("user-agent"),
        _forward_anthropic_headers(request.headers),
    )


async def proxy_openai_embeddings(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
) -> Response:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail="Embeddings request body must be a JSON object",
        )
    body.pop("stream", None)
    return await _proxy_protocol(
        ProtocolKind.OPENAI_EMBEDDING,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


async def proxy_rerank(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
) -> Response:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail="Rerank request body must be a JSON object",
        )
    body.pop("stream", None)
    return await _proxy_protocol(
        ProtocolKind.RERANK,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


_OPENAI_LIST_PROTOCOLS: frozenset[ProtocolKind] = frozenset(
    {
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
        ProtocolKind.OPENAI_EMBEDDING,
        ProtocolKind.RERANK,
    }
)

_ALL_MODEL_LIST_PROTOCOLS: frozenset[ProtocolKind] = frozenset(ProtocolKind)


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


def _build_openai_models_payload(
    groups: list[ModelGroup],
    gateway_key: GatewayApiKey,
    protocols: frozenset[ProtocolKind] | set[ProtocolKind] = _OPENAI_LIST_PROTOCOLS,
) -> dict[str, Any]:
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


def _build_anthropic_models_payload(
    groups: list[ModelGroup], gateway_key: GatewayApiKey
) -> dict[str, Any]:
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


def _build_gemini_models_payload(
    groups: list[ModelGroup], gateway_key: GatewayApiKey
) -> dict[str, Any]:
    names = _filtered_group_names(groups, gateway_key, frozenset({ProtocolKind.GEMINI}))
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


async def list_gateway_models(
    request: Request,
    gateway_key: GatewayApiKey = Depends(get_current_gateway_key),
) -> dict[str, Any]:
    groups = await app_state.domain_store.list_groups()
    runtime = await app_state.domain_store.get_runtime_settings()
    if runtime["model_list_compat_mode_enabled"]:
        return _build_openai_models_payload(
            groups, gateway_key, _ALL_MODEL_LIST_PROTOCOLS
        )
    if request.headers.get("anthropic-version"):
        return _build_anthropic_models_payload(groups, gateway_key)
    return _build_openai_models_payload(groups, gateway_key)


async def list_gemini_models(
    gateway_key: GatewayApiKey = Depends(get_current_gateway_key),
) -> dict[str, Any]:
    groups = await app_state.domain_store.list_groups()
    return _build_gemini_models_payload(groups, gateway_key)


async def proxy_gemini_generate_content(
    model_name: str,
    request: Request,
    gateway_key: GatewayApiKey = Depends(get_current_gateway_key),
) -> Response:
    body = await request.json()
    body = {**body, "model": model_name, "stream": False}
    return await _proxy_protocol(
        ProtocolKind.GEMINI,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


async def proxy_gemini_stream_generate_content(
    model_name: str,
    request: Request,
    gateway_key: GatewayApiKey = Depends(get_current_gateway_key),
) -> Response:
    body = await request.json()
    body = {**body, "model": model_name, "stream": True}
    return await _proxy_protocol(
        ProtocolKind.GEMINI,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )
