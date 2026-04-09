from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route(
        "/api/admin/overview",
        service_module.overview_metrics,
        methods=["GET"],
        response_model=service_module.OverviewMetrics,
    )
    app.add_api_route(
        "/api/admin/overview-summary",
        service_module.overview_summary,
        methods=["GET"],
        response_model=service_module.OverviewSummary,
    )
    app.add_api_route(
        "/api/admin/overview-daily",
        service_module.overview_daily,
        methods=["GET"],
        response_model=list[service_module.OverviewDailyPoint],
    )
    app.add_api_route(
        "/api/admin/overview-models",
        service_module.overview_models,
        methods=["GET"],
        response_model=service_module.OverviewModelAnalytics,
    )
