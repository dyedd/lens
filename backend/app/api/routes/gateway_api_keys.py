from fastapi import FastAPI

from ...gateway.service.admin.gateway_api_keys import (
    create_gateway_api_key,
    delete_gateway_api_key,
    list_gateway_api_keys,
    update_gateway_api_key,
)
from ...models.gateway_keys import GatewayApiKey


def register(app: FastAPI) -> None:
    app.add_api_route(
        "/api/admin/gateway-api-keys",
        list_gateway_api_keys,
        methods=["GET"],
        response_model=list[GatewayApiKey],
    )
    app.add_api_route(
        "/api/admin/gateway-api-keys",
        create_gateway_api_key,
        methods=["POST"],
        response_model=GatewayApiKey,
    )
    app.add_api_route(
        "/api/admin/gateway-api-keys/{key_id}",
        update_gateway_api_key,
        methods=["PUT"],
        response_model=GatewayApiKey,
    )
    app.add_api_route(
        "/api/admin/gateway-api-keys/{key_id}",
        delete_gateway_api_key,
        methods=["DELETE"],
        status_code=204,
    )
