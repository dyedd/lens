from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from http import HTTPStatus
from typing import Any

import jwt
from fastapi import FastAPI, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ...models import ErrorResponse, ProtocolKind
from ..cronjob_runner import CronjobAlreadyRunningError
from .state import app_state, logger


def register_exception_handlers(app: FastAPI) -> None:
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


def _error_response(
    *,
    status_code: int,
    error_type: str,
    message: str,
    details: Any | None = None,
    headers: Mapping[str, str] | None = None,
    request: Request | None = None,
) -> JSONResponse:
    protocol = _request_error_protocol(request)
    if protocol is not None:
        return _protocol_error_response(
            protocol=protocol,
            status_code=status_code,
            error_type=error_type,
            message=message,
            headers=headers,
        )
    error: dict[str, Any] = {"type": error_type, "message": message}
    if details is not None:
        error["details"] = jsonable_encoder(details)
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=error).model_dump(mode="json"),
        headers=dict(headers) if headers else None,
    )


def _request_error_protocol(request: Request | None) -> ProtocolKind | None:
    if request is None:
        return None
    path = request.url.path.rstrip("/")
    if path.startswith("/v1beta/"):
        return ProtocolKind.GEMINI
    if path == "/v1/messages":
        return ProtocolKind.ANTHROPIC
    if path == "/v1/models" and request.headers.get("anthropic-version"):
        return ProtocolKind.ANTHROPIC
    if path in {
        "/v1/chat/completions",
        "/v1/responses",
        "/v1/embeddings",
        "/v1/rerank",
        "/v1/models",
    }:
        return ProtocolKind.OPENAI_CHAT
    return None


def _protocol_error_response(
    *,
    protocol: ProtocolKind,
    status_code: int,
    error_type: str,
    message: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    content = _protocol_error_payload(
        protocol=protocol,
        status_code=status_code,
        error_type=error_type,
        message=message,
    )
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=dict(headers) if headers else None,
    )


def _protocol_error_payload(
    *,
    protocol: ProtocolKind,
    status_code: int,
    error_type: str,
    message: str,
) -> dict[str, Any]:
    if protocol == ProtocolKind.ANTHROPIC:
        return {
            "type": "error",
            "error": {
                "type": _anthropic_error_type(status_code, error_type),
                "message": message,
            },
        }
    if protocol == ProtocolKind.GEMINI:
        return {
            "error": {
                "code": status_code,
                "message": message,
                "status": _gemini_error_status(status_code),
            }
        }
    return {
        "error": {
            "message": message,
            "type": error_type,
            "param": None,
            "code": None,
        }
    }


def _anthropic_error_type(status_code: int, error_type: str) -> str:
    if status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
        return "authentication_error"
    if status_code == status.HTTP_404_NOT_FOUND:
        return "not_found_error"
    if status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return "rate_limit_error"
    if status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
        return "invalid_request_error"
    if status_code >= 500:
        return "api_error"
    if error_type in {"bad_request", "validation_error"}:
        return "invalid_request_error"
    return "api_error"


def _gemini_error_status(status_code: int) -> str:
    if status_code == status.HTTP_400_BAD_REQUEST:
        return "INVALID_ARGUMENT"
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "UNAUTHENTICATED"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "PERMISSION_DENIED"
    if status_code == status.HTTP_404_NOT_FOUND:
        return "NOT_FOUND"
    if status_code == status.HTTP_409_CONFLICT:
        return "ABORTED"
    if status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return "RESOURCE_EXHAUSTED"
    if status_code == status.HTTP_504_GATEWAY_TIMEOUT:
        return "DEADLINE_EXCEEDED"
    if status_code >= 500:
        return "INTERNAL"
    return "UNKNOWN"


def _status_error_type(status_code: int) -> str:
    if status_code == status.HTTP_400_BAD_REQUEST:
        return "bad_request"
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "unauthorized"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "forbidden"
    if status_code == status.HTTP_404_NOT_FOUND:
        return "not_found"
    if status_code == status.HTTP_409_CONFLICT:
        return "conflict"
    if status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
        return "validation_error"
    if status_code >= 500:
        return "server_error"
    return "http_error"


def _status_message(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Request failed"


def _detail_message(detail: Any, fallback: str) -> str:
    if isinstance(detail, str) and detail:
        return detail
    if isinstance(detail, Mapping):
        message = detail.get("message")
        if isinstance(message, str) and message:
            return message
    return fallback


def _key_error_message(exc: KeyError) -> str:
    if not exc.args:
        return "Resource not found"
    key = exc.args[0]
    return f"Resource not found: {key}"


def _database_error_response(
    exc: OperationalError, request: Request | None = None
) -> JSONResponse:
    message = str(exc.orig if hasattr(exc, "orig") else exc).lower()
    if "database is locked" in message:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail = "Database is busy, please retry"
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        detail = "Database operation failed"
    return _error_response(
        status_code=status_code,
        error_type="database_error",
        message=detail,
        request=request,
    )


async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    status_code = int(exc.status_code)
    detail = getattr(exc, "detail", None)
    details = None
    if isinstance(detail, Mapping) and "details" in detail:
        details = detail["details"]
    return _error_response(
        status_code=status_code,
        error_type=_status_error_type(status_code),
        message=_detail_message(detail, _status_message(status_code)),
        details=details,
        headers=getattr(exc, "headers", None),
        request=request,
    )


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_type="validation_error",
        message="Request validation failed",
        details=exc.errors(),
        request=request,
    )


async def handle_invalid_token_error(
    request: Request, __: jwt.InvalidTokenError
) -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        error_type="unauthorized",
        message="Invalid token",
        request=request,
    )


async def handle_cronjob_already_running(
    request: Request, exc: CronjobAlreadyRunningError
) -> JSONResponse:
    task_id = exc.args[0] if exc.args else ""
    message = f"Cron job is already running: {task_id}" if task_id else str(exc)
    return _error_response(
        status_code=status.HTTP_409_CONFLICT,
        error_type="conflict",
        message=message,
        request=request,
    )


async def handle_key_error(request: Request, exc: KeyError) -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        error_type="not_found",
        message=_key_error_message(exc),
        request=request,
    )


async def handle_lookup_error(request: Request, exc: LookupError) -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        error_type="not_found",
        message=str(exc) or "Resource not found",
        request=request,
    )


async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_type="bad_request",
        message=str(exc) or "Invalid request",
        request=request,
    )


async def handle_json_decode_error(
    request: Request, __: json.JSONDecodeError
) -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_type="bad_request",
        message="Invalid JSON payload",
        request=request,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error")
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type="server_error",
        message="Internal server error",
        request=request,
    )


def _apply_router_runtime_settings(runtime: dict[str, Any]) -> None:
    app_state.router.configure_health_scoring(
        health_window_seconds=int(runtime["health_window_seconds"]),
        health_penalty_weight=float(runtime["health_penalty_weight"]),
        health_min_samples=int(runtime["health_min_samples"]),
    )


async def handle_operational_error(
    request: Request, exc: OperationalError
) -> JSONResponse:
    return _database_error_response(exc, request)


async def dynamic_cors_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    try:
        runtime = await app_state.settings_repo.get_runtime_settings()
        _apply_router_runtime_settings(runtime)
    except OperationalError as exc:
        return _database_error_response(exc, request)
    allow_origins = runtime["cors_allow_origins"]
    origin = request.headers.get("origin", "")
    if allow_origins == ["*"]:
        response.headers["access-control-allow-origin"] = "*"
    elif origin and origin in allow_origins:
        response.headers["access-control-allow-origin"] = origin
        response.headers["vary"] = "Origin"
    response.headers["access-control-allow-credentials"] = "true"
    response.headers["access-control-allow-methods"] = "*"
    response.headers["access-control-allow-headers"] = "*"
    return response


async def cors_preflight(path: str, request: Request) -> Response:
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
