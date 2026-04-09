from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route("/api/admin/sites", service_module.list_sites, methods=["GET"])
    app.add_api_route("/api/admin/sites", service_module.create_site, methods=["POST"], status_code=201)
    app.add_api_route("/api/admin/sites/{site_id}", service_module.update_site, methods=["PUT"])
    app.add_api_route("/api/admin/sites/{site_id}", service_module.delete_site, methods=["DELETE"], status_code=204)
    app.add_api_route(
        "/api/admin/site-model-discoveries",
        service_module.fetch_site_models,
        methods=["POST"],
        response_model=list[service_module.SiteModelFetchItem],
    )
