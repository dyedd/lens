from __future__ import annotations

from fastapi import FastAPI

from .routes import include_routes


def create_app(service_module) -> FastAPI:
    app = FastAPI(title=service_module.settings.app_name, lifespan=service_module.lifespan)
    app.middleware("http")(service_module.dynamic_cors_middleware)
    include_routes(app, service_module)
    return app
