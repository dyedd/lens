from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx

from ...models import ProtocolKind
from .runtime_types import StreamCapture, _RequestDeadline
from .stream_detection import _cancel_stream_capture
from .stream_events import _capture_stream_event_chunk, _flush_stream_event_buffer


async def _stream_upstream_iterator(
    response: httpx.Response,
    protocol: ProtocolKind,
    capture: StreamCapture,
    stream_started_at: float,
) -> AsyncIterator[bytes]:
    deadline = capture.deadline
    assert deadline is not None
    try:
        iterator = response.aiter_bytes().__aiter__()
        while True:
            try:
                chunk = await _next_stream_chunk(iterator, deadline)
            except StopAsyncIteration:
                break
            if not chunk:
                continue
            text = chunk.decode("utf-8", errors="replace")
            if text:
                _capture_stream_event_chunk(protocol, capture, text, stream_started_at)
                if capture.capture_body:
                    capture.response_content_chunks.append(text)
            yield chunk
        _flush_stream_event_buffer(protocol, capture, stream_started_at)
        capture.is_completed = True
    except asyncio.CancelledError:
        capture.error_status_code = 499
        await _cancel_stream_capture(capture, "client disconnected")
        raise
    except TimeoutError:
        capture.error_status_code = 504
        capture.errors.append(deadline.timeout_message())
    except httpx.HTTPError as exc:
        capture.error_status_code = 502
        capture.errors.append(f"stream failed: {type(exc).__name__}: {exc}")
    finally:
        await response.aclose()


async def _next_stream_chunk(
    iterator: AsyncIterator[bytes], deadline: _RequestDeadline
) -> bytes:
    remaining = deadline.remaining_seconds()
    if remaining is None:
        return await iterator.__anext__()
    if remaining <= 0:
        raise TimeoutError(deadline.timeout_message())
    async with asyncio.timeout(remaining):
        return await iterator.__anext__()


async def _capture_converted_stream_iterator(
    raw_iterator: AsyncIterator[bytes], capture: StreamCapture
) -> AsyncIterator[bytes]:
    try:
        async for chunk in raw_iterator:
            text = chunk.decode("utf-8", errors="replace")
            if text and capture.capture_body:
                capture.client_response_content_chunks.append(text)
            yield chunk
    except asyncio.CancelledError:
        await _cancel_stream_capture(capture, "client disconnected")
        raise
    except ValueError as exc:
        await _cancel_stream_capture(capture, str(exc))
