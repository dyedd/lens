from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from ...models import ErrorResponse, ProtocolKind


def build_error_response(
    *,
    status_code: int,
    error_type: str,
    message: str,
    details: Any | None = None,
    headers: Mapping[str, str] | None = None,
    request: Request | None = None,
) -> JSONResponse:
    """Build an API- or protocol-shaped error response."""
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


def build_database_error_response(
    exc: OperationalError, request: Request | None = None
) -> JSONResponse:
    """Build the stable response for a database operational failure."""
    message = str(exc.orig if hasattr(exc, "orig") else exc).lower()
    if "database is locked" in message:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail = "Database is busy, please retry"
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        detail = "Database operation failed"
    return build_error_response(
        status_code=status_code,
        error_type="database_error",
        message=detail,
        request=request,
    )


def status_error_type(status_code: int) -> str:
    """Map an HTTP status code to the Lens error type."""
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
    if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
        return "validation_error"
    if status_code >= 500:
        return "server_error"
    return "http_error"


def status_message(status_code: int) -> str:
    """Return the standard phrase for an HTTP status code."""
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Request failed"


def detail_message(detail: Any, fallback: str) -> str:
    """Extract a stable human-readable message from exception detail."""
    if isinstance(detail, str) and detail:
        return detail
    if isinstance(detail, Mapping):
        message = detail.get("message")
        if isinstance(message, str) and message:
            return message
    return fallback


def key_error_message(exc: KeyError) -> str:
    """Format a missing-resource message from a key error."""
    if not exc.args:
        return "Resource not found"
    return f"Resource not found: {exc.args[0]}"


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
    return JSONResponse(
        status_code=status_code,
        content=_protocol_error_payload(
            protocol=protocol,
            status_code=status_code,
            error_type=error_type,
            message=message,
        ),
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
    if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
        return "invalid_request_error"
    if status_code >= 500:
        return "api_error"
    if error_type in {"bad_request", "validation_error"}:
        return "invalid_request_error"
    return "api_error"


def _gemini_error_status(status_code: int) -> str:
    statuses = {
        status.HTTP_400_BAD_REQUEST: "INVALID_ARGUMENT",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHENTICATED",
        status.HTTP_403_FORBIDDEN: "PERMISSION_DENIED",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_409_CONFLICT: "ABORTED",
        status.HTTP_429_TOO_MANY_REQUESTS: "RESOURCE_EXHAUSTED",
        status.HTTP_504_GATEWAY_TIMEOUT: "DEADLINE_EXCEEDED",
    }
    if status_code in statuses:
        return statuses[status_code]
    if status_code >= 500:
        return "INTERNAL"
    return "UNKNOWN"
