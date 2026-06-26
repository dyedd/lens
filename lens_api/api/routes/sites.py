from types import ModuleType

from fastapi import FastAPI


def register(app: FastAPI, service_module: ModuleType) -> None:
    app.add_api_route("/api/admin/sites", service_module.list_sites, methods=["GET"])
    app.add_api_route(
        "/api/admin/sites/runtime",
        service_module.site_runtime_summaries,
        methods=["GET"],
        response_model=list[service_module.SiteRuntimeSummary],
    )
    app.add_api_route(
        "/api/admin/sites",
        service_module.create_site,
        methods=["POST"],
        status_code=201,
    )
    app.add_api_route(
        "/api/admin/sites/import",
        service_module.import_sites,
        methods=["POST"],
        response_model=service_module.SiteBatchImportResult,
    )
    app.add_api_route(
        "/api/admin/sites/{site_id}", service_module.update_site, methods=["PUT"]
    )
    app.add_api_route(
        "/api/admin/sites/{site_id}",
        service_module.delete_site,
        methods=["DELETE"],
        status_code=204,
    )
    app.add_api_route(
        "/api/admin/site-model-discoveries",
        service_module.fetch_site_models,
        methods=["POST"],
        response_model=list[service_module.SiteModelFetchItem],
    )
    app.add_api_route(
        "/api/admin/site-model-tests",
        service_module.test_site_model,
        methods=["POST"],
        response_model=service_module.SiteModelTestResult,
    )
    app.add_api_route(
        "/api/admin/channel-model-sync",
        service_module.sync_channel_models,
        methods=["POST"],
        response_model=service_module.ChannelModelSyncResponse,
    )
