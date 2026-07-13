from types import ModuleType

from fastapi import FastAPI


def register(app: FastAPI, service_module: ModuleType) -> None:
    app.add_api_route(
        "/api/admin/overview-summary",
        service_module.get_overview_summary,
        methods=["GET"],
        response_model=service_module.OverviewSummary,
    )
    app.add_api_route(
        "/api/admin/overview-daily",
        service_module.list_overview_daily,
        methods=["GET"],
        response_model=list[service_module.OverviewDailyPoint],
    )
    app.add_api_route(
        "/api/admin/overview-models",
        service_module.get_overview_model_analytics,
        methods=["GET"],
        response_model=service_module.OverviewModelAnalytics,
    )
