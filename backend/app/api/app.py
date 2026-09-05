from fastapi import FastAPI
from starlette.middleware.gzip import GZipMiddleware

from ..gateway.service.http_handlers import (
    dynamic_cors_middleware,
    register_exception_handlers,
)
from ..gateway.service.lifecycle import lifespan
from .routes import include_routes


def create_app(ui_static_dir: str = "") -> FastAPI:
    """Create and configure the Lens FastAPI application."""
    app = FastAPI(title="Lens", lifespan=lifespan)
    app.middleware("http")(dynamic_cors_middleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
    register_exception_handlers(app)
    include_routes(app, ui_static_dir=ui_static_dir)
    return app
