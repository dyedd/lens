from types import ModuleType

from fastapi import FastAPI

from .routes import include_routes


def create_app(service_module: ModuleType) -> FastAPI:
    """Create and configure the Lens FastAPI application."""
    app = FastAPI(
        title=service_module.settings.app_name, lifespan=service_module.lifespan
    )
    app.middleware("http")(service_module.dynamic_cors_middleware)
    service_module.register_exception_handlers(app)
    include_routes(app, service_module)
    return app
