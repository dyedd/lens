from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import jwt
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..cronjob_runner import CronjobAlreadyRunningError
from .app_state import app_state, logger
from .error_responses import (
    _protocol_error_response,
    build_database_error_response,
    build_error_response,
    detail_message,
    key_error_message,
    status_error_type,
    status_message,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Register the application's exception-to-response handlers."""
    exception_mapping: list[tuple[type[Exception], Callable]] = [
        (StarletteHTTPException, handle_http_exception),
        (RequestValidationError, handle_validation_error),
        (OperationalError, handle_operational_error),
        (jwt.InvalidTokenError, handle_invalid_token_error),
        (CronjobAlreadyRunningError, handle_cronjob_already_running),
        (KeyError, handle_key_error),
        (LookupError, handle_lookup_error),
        (ValueError, handle_value_error),
        (json.JSONDecodeError, handle_json_decode_error),
        (Exception, handle_unexpected_error),
    ]
    for exc_class, handler in exception_mapping:
        app.add_exception_handler(exc_class, handler)


async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Convert an HTTP exception into the request protocol's error shape."""
    status_code = int(exc.status_code)
    detail = getattr(exc, "detail", None)
    details = None
    if isinstance(detail, Mapping) and "details" in detail:
        details = detail["details"]
    return build_error_response(
        status_code=status_code,
        error_type=status_error_type(status_code),
        message=detail_message(detail, status_message(status_code)),
        details=details,
        headers=getattr(exc, "headers", None),
        request=request,
    )


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert request validation failures into a stable error response."""
    return build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_type="validation_error",
        message="Request validation failed",
        details=exc.errors(),
        request=request,
    )


async def handle_invalid_token_error(
    request: Request, __: jwt.InvalidTokenError
) -> JSONResponse:
    """Return the stable authentication response for an invalid token."""
    return build_error_response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        error_type="unauthorized",
        message="Invalid token",
        request=request,
    )


async def handle_cronjob_already_running(
    request: Request, exc: CronjobAlreadyRunningError
) -> JSONResponse:
    """Return a conflict response for a concurrently running cron job."""
    task_id = exc.args[0] if exc.args else ""
    message = f"Cron job is already running: {task_id}" if task_id else str(exc)
    return build_error_response(
        status_code=status.HTTP_409_CONFLICT,
        error_type="conflict",
        message=message,
        request=request,
    )


async def handle_key_error(request: Request, exc: KeyError) -> JSONResponse:
    """Return a missing-resource response for a key lookup failure."""
    return build_error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        error_type="not_found",
        message=key_error_message(exc),
        request=request,
    )


async def handle_lookup_error(request: Request, exc: LookupError) -> JSONResponse:
    """Return a missing-resource response for a lookup failure."""
    return build_error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        error_type="not_found",
        message=str(exc) or "Resource not found",
        request=request,
    )


async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    """Return a bad-request response for invalid application values."""
    return build_error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_type="bad_request",
        message=str(exc) or "Invalid request",
        request=request,
    )


async def handle_json_decode_error(
    request: Request, __: json.JSONDecodeError
) -> JSONResponse:
    """Return a bad-request response for malformed JSON."""
    return build_error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_type="bad_request",
        message="Invalid JSON payload",
        request=request,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Log and hide unexpected application failures."""
    logger.exception("Unhandled API error")
    return build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type="server_error",
        message="Internal server error",
        request=request,
    )


async def handle_operational_error(
    request: Request, exc: OperationalError
) -> JSONResponse:
    """Convert a database operational failure into a stable response."""
    return build_database_error_response(exc, request)


def _apply_router_runtime_settings(runtime: dict[str, Any]) -> None:
    app_state.router.configure_health_scoring(
        health_window_seconds=int(runtime["health_window_seconds"]),
        health_penalty_weight=float(runtime["health_penalty_weight"]),
        health_min_samples=int(runtime["health_min_samples"]),
    )


async def dynamic_cors_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Apply runtime CORS settings and router health configuration."""
    response = await call_next(request)
    try:
        runtime = await app_state.settings_repo.get_runtime_settings()
        _apply_router_runtime_settings(runtime)
    except OperationalError as exc:
        return build_database_error_response(exc, request)
    allow_origins = runtime["cors_allow_origins"]
    origin = request.headers.get("origin", "")
    if allow_origins == ["*"]:
        response.headers["access-control-allow-origin"] = "*"
    elif origin and origin in allow_origins:
        response.headers["access-control-allow-origin"] = origin
        response.headers["vary"] = "Origin"
    response.headers.setdefault("access-control-allow-credentials", "true")
    response.headers.setdefault("access-control-allow-methods", "*")
    response.headers.setdefault("access-control-allow-headers", "*")
    return response


async def handle_cors_preflight(path: str, request: Request) -> Response:
    """Return a preflight response using the configured allowed origins."""
    runtime = await app_state.settings_repo.get_runtime_settings()
    _apply_router_runtime_settings(runtime)
    allow_origins = runtime["cors_allow_origins"]
    origin = request.headers.get("origin", "")
    headers = {
        "access-control-allow-credentials": "true",
        "access-control-allow-methods": "*",
        "access-control-allow-headers": request.headers.get(
            "access-control-request-headers", "*"
        ),
    }
    if allow_origins == ["*"]:
        headers["access-control-allow-origin"] = "*"
    elif origin and origin in allow_origins:
        headers["access-control-allow-origin"] = origin
        headers["vary"] = "Origin"
    return Response(status_code=204, headers=headers)
