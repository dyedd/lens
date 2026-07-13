from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, Response
from starlette.datastructures import UploadFile

from ...models import GatewayApiKey, ProtocolKind
from .app_state import app_state
from .auth import get_current_gateway_key
from .model_list_payloads import (
    ALL_MODEL_LIST_PROTOCOLS,
    build_anthropic_models_payload,
    build_gemini_models_payload,
    build_openai_models_payload,
)
from .proxy_flow import _proxy_protocol
from .upstream_support import _forward_anthropic_headers


async def _read_json_object(request: Request, body_name: str) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=f"{body_name} request body must be a JSON object",
        )
    return body


async def proxy_openai_chat(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
) -> Response:
    """Proxy an authenticated OpenAI chat completion request."""
    body = await _read_json_object(request, "Chat completion")
    return await _proxy_protocol(
        ProtocolKind.OPENAI_CHAT,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


async def proxy_openai_responses(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
) -> Response:
    """Proxy an authenticated OpenAI Responses request."""
    body = await _read_json_object(request, "Responses")
    return await _proxy_protocol(
        ProtocolKind.OPENAI_RESPONSES,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


async def proxy_anthropic_messages(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
) -> Response:
    """Proxy an authenticated Anthropic Messages request."""
    body = await _read_json_object(request, "Anthropic messages")
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
    """Proxy an authenticated OpenAI embeddings request without streaming."""
    body = await _read_json_object(request, "Embeddings")
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
    """Proxy an authenticated rerank request without streaming."""
    body = await _read_json_object(request, "Rerank")
    body.pop("stream", None)
    return await _proxy_protocol(
        ProtocolKind.RERANK,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


async def proxy_openai_image_generations(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
) -> Response:
    """Proxy an authenticated OpenAI image generation request."""
    body = await _read_json_object(request, "Image generations")
    return await _proxy_protocol(
        ProtocolKind.OPENAI_IMAGE,
        body,
        gateway_key,
        request.headers.get("user-agent"),
        path_suffix="images/generations",
    )


async def proxy_openai_image_edits(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
) -> Response:
    """Proxy an authenticated multipart OpenAI image edit request."""
    form = await request.form()
    fields: dict[str, str] = {}
    files: list[tuple[str, tuple[str, bytes, str]]] = []
    for field_name, value in form.multi_items():
        if isinstance(value, UploadFile):
            files.append(
                (
                    field_name,
                    (
                        value.filename or field_name,
                        await value.read(),
                        value.content_type or "application/octet-stream",
                    ),
                )
            )
        else:
            fields[field_name] = value
    return await _proxy_protocol(
        ProtocolKind.OPENAI_IMAGE,
        dict(fields),
        gateway_key,
        request.headers.get("user-agent"),
        path_suffix="images/edits",
        multipart_files=files,
    )


async def list_gateway_models(
    request: Request,
    gateway_key: GatewayApiKey = Depends(get_current_gateway_key),
) -> dict[str, Any]:
    """List model groups visible to the gateway key in the requested API format."""
    groups = await app_state.group_repo.list_groups()
    runtime = await app_state.settings_repo.get_runtime_settings()
    if runtime["model_list_compat_mode_enabled"]:
        return build_openai_models_payload(
            groups, gateway_key, ALL_MODEL_LIST_PROTOCOLS
        )
    if request.headers.get("anthropic-version"):
        return build_anthropic_models_payload(groups, gateway_key)
    return build_openai_models_payload(groups, gateway_key)


async def list_gemini_models(
    gateway_key: GatewayApiKey = Depends(get_current_gateway_key),
) -> dict[str, Any]:
    """List Gemini-compatible model groups visible to the gateway key."""
    groups = await app_state.group_repo.list_groups()
    return build_gemini_models_payload(groups, gateway_key)


async def proxy_gemini_generate_content(
    model_name: str,
    request: Request,
    gateway_key: GatewayApiKey = Depends(get_current_gateway_key),
) -> Response:
    """Proxy an authenticated non-streaming Gemini content request."""
    body = await _read_json_object(request, "Gemini generateContent")
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
    """Proxy an authenticated streaming Gemini content request."""
    body = await _read_json_object(request, "Gemini streamGenerateContent")
    body = {**body, "model": model_name, "stream": True}
    return await _proxy_protocol(
        ProtocolKind.GEMINI,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )
