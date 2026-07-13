from __future__ import annotations

from typing import Any

from fastapi import Depends

from ....models import ModelPriceItem, ModelPriceListResponse, ModelPriceUpdate
from ..auth import get_current_admin
from ..app_state import app_state
from ..model_price_tasks import _sync_group_prices


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
    await _sync_group_prices(app_state, overwrite_existing=True)
    return await app_state.model_price_repo.list_model_prices()
