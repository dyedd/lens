from __future__ import annotations

from typing import Any

from fastapi import Depends, Response

from ....models import GatewayApiKey, GatewayApiKeyCreate, GatewayApiKeyUpdate
from ..auth import get_current_admin
from ..app_state import app_state


async def list_gateway_api_keys(
    _: Any = Depends(get_current_admin),
) -> list[GatewayApiKey]:
    """List gateway API keys."""
    return await app_state.gateway_api_key_repo.list_gateway_api_keys()


async def create_gateway_api_key(
    payload: GatewayApiKeyCreate, _: Any = Depends(get_current_admin)
) -> GatewayApiKey:
    """Create a gateway API key."""
    return await app_state.gateway_api_key_repo.create_gateway_api_key(payload)


async def update_gateway_api_key(
    key_id: str, payload: GatewayApiKeyUpdate, _: Any = Depends(get_current_admin)
) -> GatewayApiKey:
    """Update a gateway API key."""
    return await app_state.gateway_api_key_repo.update_gateway_api_key(key_id, payload)


async def delete_gateway_api_key(
    key_id: str, _: Any = Depends(get_current_admin)
) -> Response:
    """Delete a gateway API key."""
    await app_state.gateway_api_key_repo.delete_gateway_api_key(key_id)
    return Response(status_code=204)
