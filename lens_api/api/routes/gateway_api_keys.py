from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route(
        "/api/admin/gateway-api-keys",
        service_module.list_gateway_api_keys,
        methods=["GET"],
        response_model=list[service_module.GatewayApiKey],
    )
    app.add_api_route(
        "/api/admin/gateway-api-keys",
        service_module.create_gateway_api_key,
        methods=["POST"],
        response_model=service_module.GatewayApiKey,
    )
    app.add_api_route(
        "/api/admin/gateway-api-keys/{key_id}",
        service_module.update_gateway_api_key,
        methods=["PUT"],
        response_model=service_module.GatewayApiKey,
    )
    app.add_api_route(
        "/api/admin/gateway-api-keys/{key_id}",
        service_module.delete_gateway_api_key,
        methods=["DELETE"],
        status_code=204,
    )
