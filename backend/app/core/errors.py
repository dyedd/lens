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


class StoredDataError(LensError):
    def __init__(self) -> None:
        super().__init__("Stored data is invalid")


class RoutingError(LensError):
    """No usable route matches the requested protocol or model."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503, error_type="routing_error")


class ResourceConflictError(LensError):
    """A requested change conflicts with the current state of a resource."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409, error_type="conflict")


class RequestCancelledError(LensError):
    def __init__(self) -> None:
        super().__init__(
            "Request cancelled by administrator",
            status_code=499,
            error_type="request_cancelled",
        )


class ModelDiscoveryError(LensError):
    """An upstream model catalog could not be fetched or parsed."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(
            message,
            status_code=status_code,
            error_type="model_discovery_error",
        )


class ModelCatalogIncompleteError(ModelDiscoveryError):
    """目录已开始返回，但分页未完成，不能换协议后使用另一份目录。"""
