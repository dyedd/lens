from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from .routes import include_routes


def create_app(service_module) -> FastAPI:
    app = FastAPI(title=service_module.settings.app_name, lifespan=service_module.lifespan)
    app.middleware("http")(service_module.dynamic_cors_middleware)
    app.add_exception_handler(OperationalError, service_module.handle_operational_error)
    include_routes(app, service_module)
    return app
