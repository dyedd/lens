from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException

from ....models.model_prices import (
    ModelPriceItem,
    ModelPriceListResponse,
    ModelPriceUpdate,
)
from ..app_state import app_state
from ..auth import get_current_admin
from ..model_price_tasks import ModelPriceSyncError, _sync_group_prices


async def list_model_prices(
    _: Any = Depends(get_current_admin),
) -> ModelPriceListResponse:
    """List configured model prices."""
    return await app_state.model_price_repo.list_model_prices()


async def update_model_price(
    model_key: str, payload: ModelPriceUpdate, _: Any = Depends(get_current_admin)
) -> ModelPriceItem:
    """Create or update the price for a model group."""
    return await app_state.model_price_repo.upsert_model_price(
        payload.model_copy(update={"model_key": model_key})
    )


async def sync_model_prices(
    _: Any = Depends(get_current_admin),
) -> ModelPriceListResponse:
    """Refresh model prices and return the resulting list."""
    try:
        await _sync_group_prices(app_state)
    except ModelPriceSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return await app_state.model_price_repo.list_model_prices()
