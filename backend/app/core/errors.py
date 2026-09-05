from __future__ import annotations

from typing import Any


class LensError(Exception):
    """An expected application failure with a stable public error contract."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        error_type: str = "server_error",
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.public_message = message
        self.details = details


class ResourceNotFoundError(LensError):
    """An expected lookup failed at an API resource boundary."""

    def __init__(self, resource_id: object) -> None:
        super().__init__(
            f"Resource not found: {resource_id}",
            status_code=404,
            error_type="not_found",
        )


class RoutingError(LensError):
    """No usable route matches the requested protocol or model."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503, error_type="routing_error")
