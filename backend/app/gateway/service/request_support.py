"""Measure request timing and enforce gateway request limits."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from .runtime_types import GatewayTimeoutError


def elapsed_ms(started_at: float) -> int:
    return max(int((perf_counter() - started_at) * 1000), 0)


@asynccontextmanager
async def gateway_timeout_scope(
    wait: float | None, *, timeout_message: str
) -> AsyncIterator[None]:
    """Bound a critical section without rewriting unrelated TimeoutError values."""
    if wait is None:
        yield
        return
    if wait <= 0:
        raise GatewayTimeoutError(timeout_message)
    timeout_scope = asyncio.timeout(wait)
    try:
        async with timeout_scope:
            yield
    except TimeoutError as exc:
        if not timeout_scope.expired():
            raise
        raise GatewayTimeoutError(timeout_message) from exc


def request_body_too_large_message(size: int, limit: int) -> str | None:
    bounded_limit = max(int(limit), 0)
    if bounded_limit <= 0 or size <= bounded_limit:
        return None
    return (
        f"Request body is {size} bytes, exceeds Lens limit "
        f"{bounded_limit} bytes. Split the context or increase "
        "the maximum request body size in Settings."
    )
