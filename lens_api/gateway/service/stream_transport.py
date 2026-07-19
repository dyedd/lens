from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
from fastapi.responses import StreamingResponse
from starlette.requests import ClientDisconnect
from starlette.types import Receive, Scope, Send

from ...models import ProtocolKind
from .runtime_types import (
    StreamCapture,
    _RequestDeadline,
    _capture_stream_content,
    _record_stream_error,
)
from .stream_detection import _cancel_stream_capture
from .stream_events import _capture_stream_event_chunk, _flush_stream_event_buffer


class _FinalizingStreamingResponse(StreamingResponse):
    """Run response cleanup even when the stream iterator raises."""

    def __init__(
        self,
        content: AsyncIterator[bytes],
        *,
        stream_capture: StreamCapture,
        upstream_response: httpx.Response,
        status_code: int,
        media_type: str | None,
        headers: dict[str, str],
    ) -> None:
        super().__init__(
            content,
            status_code=status_code,
            media_type=media_type,
            headers=headers,
        )
        self._stream_capture = stream_capture
        self._upstream_response = upstream_response

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        background = self.background
        self.background = None
        try:
            await super().__call__(scope, receive, send)
            if (
                not self._stream_capture.is_client_stream_completed
                and not self._stream_capture.errors
            ):
                await _cancel_stream_capture(self._stream_capture)
        except ClientDisconnect:
            await _cancel_stream_capture(self._stream_capture)
            raise
        finally:
            try:
                close_iterator = getattr(self.body_iterator, "aclose", None)
                if close_iterator is not None:
                    await close_iterator()
            finally:
                try:
                    await self._upstream_response.aclose()
                finally:
                    if background is not None:
                        await background()


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
                _capture_stream_content(capture, text)
            yield chunk
        _flush_stream_event_buffer(protocol, capture, stream_started_at)
        capture.is_completed = True
    except asyncio.CancelledError:
        await _cancel_stream_capture(capture)
        raise
    except TimeoutError:
        _record_stream_error(capture, deadline.timeout_message(), status_code=504)
        raise
    except httpx.HTTPError as exc:
        _record_stream_error(
            capture,
            f"stream failed: {type(exc).__name__}: {exc}",
            status_code=502,
        )
        raise
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
            _capture_stream_content(capture, text, client_response=True)
            yield chunk
    except asyncio.CancelledError:
        await _cancel_stream_capture(capture)
        raise
    except ValueError as exc:
        _record_stream_error(
            capture,
            f"stream conversion failed: {exc}",
            status_code=502,
        )
        raise
