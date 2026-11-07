from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException

from ....core.errors import LensError
from ....core.model_prices import canonical_model_price_key
from ....models.model_prices import (
    ModelPriceItem,
    ModelPriceListResponse,
    ModelPriceUpdate,
)
from ..app_state import app_state
from ..auth import get_current_admin
from ..tasks.litellm_sync_tasks import ModelPriceSyncError, sync_litellm_metadata


async def list_model_prices(
    _: Any = Depends(get_current_admin),
) -> ModelPriceListResponse:
    """List configured model prices."""
    return await app_state.model_price_repo.list_model_prices()


async def update_model_price(
    model_key: str, payload: ModelPriceUpdate, _: Any = Depends(get_current_admin)
) -> ModelPriceItem:
    """Create or update the price for a model group."""
    if payload.model_key is not None and canonical_model_price_key(
        payload.model_key
    ) != canonical_model_price_key(model_key):
        raise LensError(
            "Model key must match the request path",
            status_code=400,
            error_type="bad_request",
        )
    return await app_state.model_price_repo.upsert_model_price(model_key, payload)


async def restore_model_price(
    model_key: str, _: Any = Depends(get_current_admin)
) -> ModelPriceListResponse:
    """Restore a manual price from the latest source."""
    try:
        await sync_litellm_metadata(app_state, restore_key=model_key)
    except ModelPriceSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return await app_state.model_price_repo.list_model_prices()


async def sync_model_prices(
    _: Any = Depends(get_current_admin),
) -> ModelPriceListResponse:
    """Refresh model prices and return the resulting list."""
    try:
        await sync_litellm_metadata(app_state)
    except ModelPriceSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return await app_state.model_price_repo.list_model_prices()
