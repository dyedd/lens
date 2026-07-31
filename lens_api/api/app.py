from types import ModuleType

from fastapi import FastAPI
from starlette.middleware.gzip import GZipMiddleware

from .routes import include_routes


def create_app(service_module: ModuleType, *, ui_static_dir: str = "") -> FastAPI:
    """Create and configure the Lens FastAPI application."""
    app = FastAPI(title="Lens", lifespan=service_module.lifespan)
    app.middleware("http")(service_module.dynamic_cors_middleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
    service_module.register_exception_handlers(app)
    include_routes(app, service_module, ui_static_dir=ui_static_dir)
    return app
