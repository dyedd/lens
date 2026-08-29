from fastapi import FastAPI

from ...gateway.service.admin.model_prices import sync_model_prices, update_model_price
from ...models.model_prices import ModelPriceItem, ModelPriceListResponse


def register(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/model-prices/{model_key}",
        update_model_price,
        methods=["PUT"],
        response_model=ModelPriceItem,
    )
    app.add_api_route(
        "/api/admin/model-price-sync-jobs",
        sync_model_prices,
        methods=["POST"],
        response_model=ModelPriceListResponse,
    )
