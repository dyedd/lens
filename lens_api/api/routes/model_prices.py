from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route(
        "/api/admin/model-prices/{model_key}",
        service_module.update_model_price,
        methods=["PUT"],
        response_model=service_module.ModelPriceItem,
    )
    app.add_api_route(
        "/api/admin/model-price-sync-jobs",
        service_module.sync_model_prices,
        methods=["POST"],
        response_model=service_module.ModelPriceListResponse,
    )
