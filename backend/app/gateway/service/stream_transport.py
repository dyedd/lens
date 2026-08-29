from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.types import Receive, Scope, Send

from ...models.protocols import ProtocolKind
from ..router.cooldown import ErrorCategory
from .app_state import logger
from .routing_plan import _gateway_timeout_scope
from .runtime_types import (
    StreamCapture,
    _capture_stream_content,
    _GatewayTimeoutError,
    _record_stream_error,
    _RequestDeadline,
)
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
        owned_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            content,
            status_code=status_code,
            media_type=media_type,
            headers=headers,
        )
        self._stream_capture = stream_capture
        self._upstream_response = upstream_response
        self._owned_client = owned_client

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        background = self.background
        self.background = None
        try:
            await super().__call__(scope, receive, send)
        except BaseException:
            try:
                await self._finalize(background)
            except BaseException:
                logger.exception("Failed to finalize streaming response")
            raise
        await self._finalize(background)

    async def _finalize(self, background: BackgroundTask | None) -> None:
        if (
            not self._stream_capture.is_client_stream_completed
            and not self._stream_capture.errors
        ):
            self._stream_capture.is_client_disconnected = True
        try:
            close_iterator = getattr(self.body_iterator, "aclose", None)
            if close_iterator is not None:
                await close_iterator()
        finally:
            try:
                await self._upstream_response.aclose()
            finally:
                try:
                    if self._owned_client is not None:
                        await self._owned_client.aclose()
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
    try:
        iterator: AsyncIterator[bytes] = response.aiter_bytes().__aiter__()
        while True:
            try:
                chunk = await _next_stream_chunk(
                    iterator,
                    deadline,
                    has_seen_first_chunk=capture.has_seen_first_chunk,
                )
            except StopAsyncIteration:
                _flush_stream_event_buffer(protocol, capture, stream_started_at)
                break
            if not chunk:
                continue
            text = chunk.decode("utf-8", errors="surrogateescape")
            terminal_prefix_length: int | None = None
            if text:
                terminal_prefix_length = _capture_stream_event_chunk(
                    protocol, capture, text, stream_started_at
                )
            if terminal_prefix_length is None or terminal_prefix_length >= len(text):
                forwarded_chunk = chunk
            else:
                forwarded_chunk = text[:terminal_prefix_length].encode(
                    "utf-8", errors="surrogateescape"
                )
            if terminal_prefix_length is not None:
                await response.aclose()
            if forwarded_chunk:
                _capture_stream_content(
                    capture, capture.content_decoder.decode(forwarded_chunk)
                )
                yield forwarded_chunk
            if terminal_prefix_length is not None:
                break
    except _GatewayTimeoutError as exc:
        _record_stream_error(
            capture,
            str(exc),
            status_code=504,
            category=ErrorCategory.TIMEOUT,
        )
        raise
    except httpx.HTTPError as exc:
        _record_stream_error(
            capture,
            f"stream failed: {type(exc).__name__}: {exc}",
            status_code=502,
            category=ErrorCategory.NETWORK,
        )
        raise


async def _next_stream_chunk(
    iterator: AsyncIterator[bytes],
    deadline: _RequestDeadline,
    *,
    has_seen_first_chunk: bool,
) -> bytes:
    wait = deadline.stream_chunk_wait_seconds(has_seen_first_chunk=has_seen_first_chunk)
    kind = "stream_idle" if has_seen_first_chunk else "first_token"
    async with _gateway_timeout_scope(
        wait,
        timeout_message=deadline.timeout_message(kind=kind),
    ):
        return await iterator.__anext__()


async def _capture_converted_stream_iterator(
    raw_iterator: AsyncIterator[bytes], capture: StreamCapture
) -> AsyncIterator[bytes]:
    try:
        async for chunk in raw_iterator:
            text = capture.client_content_decoder.decode(chunk)
            _capture_stream_content(capture, text, client_response=True)
            yield chunk
    except ValueError as exc:
        if not capture.errors:
            _record_stream_error(
                capture,
                f"stream conversion failed: {exc}",
                status_code=502,
            )
        raise
