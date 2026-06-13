from types import ModuleType

from fastapi import FastAPI


def register(app: FastAPI, service_module: ModuleType) -> None:
    app.add_api_route(
        "/api/admin/request-logs/page",
        service_module.request_log_page,
        methods=["GET"],
        response_model=service_module.RequestLogPage,
    )
    app.add_api_route(
        "/api/admin/request-logs",
        service_module.clear_request_logs,
        methods=["DELETE"],
        status_code=204,
    )
    app.add_api_route(
        "/api/admin/request-logs/{log_id}",
        service_module.request_log_detail,
        methods=["GET"],
        response_model=service_module.RequestLogDetail,
    )
