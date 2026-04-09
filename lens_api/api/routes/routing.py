from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route("/{path:path}", service_module.cors_preflight, methods=["OPTIONS"], status_code=204)
    app.add_api_route("/api/admin/routes", service_module.router_snapshot, methods=["GET"])
    app.add_api_route("/api/admin/route-previews", service_module.router_preview, methods=["POST"])
