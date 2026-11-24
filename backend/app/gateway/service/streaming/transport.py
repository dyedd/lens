from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import nullcontext

import anyio
import httpx
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.types import Message, Receive, Scope, Send

from ....core.errors import RequestCancelledError
from ....models.protocols import ProtocolKind
from ...router.cooldown import ErrorCategory
from ..app_state import app_state
from ..error_responses import stream_error_frame
from ..request_support import gateway_timeout_scope
from ..runtime_types import (
    GatewayTimeoutError,
    RequestDeadline,
)
from .capture import (
    StreamCapture,
    capture_stream_content,
    record_stream_error,
)
from .events import (
    _capture_stream_event_chunk,
    _flush_stream_event_buffer,
)

logger = logging.getLogger(__name__)


class FinalizingStreamingResponse(StreamingResponse):
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
        client_protocol: ProtocolKind,
    ) -> None:
        super().__init__(
            content,
            status_code=status_code,
            media_type=media_type,
            headers=headers,
        )
        self._stream_capture = stream_capture
        self._upstream_response = upstream_response
        self._client_protocol = client_protocol

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        background = self.background
        self.background = None
        log_id = self._stream_capture.request_log_id
        cancellation = (
            app_state.active_requests.get(log_id) if log_id is not None else None
        )
        response_started = False
        cancellation_error: RequestCancelledError | None = None

        async def track_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            with cancellation.watch() if cancellation else nullcontext():
                await super().__call__(scope, receive, track_send)
        except RequestCancelledError as exc:
            self._stream_capture.is_admin_cancelled = True
            cancellation_error = exc
        except BaseException:
            try:
                await self._finalize(background)
            except BaseException:
                logger.exception("Failed to finalize streaming response")
            raise
        finally:
            if log_id is not None:
                app_state.active_requests.pop(log_id, None)
        await self._finalize(background)
        if cancellation_error is not None:
            if not response_started:
                await send(
                    {
                        "type": "http.response.start",
                        "status": cancellation_error.status_code,
                        "headers": self.raw_headers,
                    }
                )
            await send(
                {
                    "type": "http.response.body",
                    "body": stream_error_frame(
                        protocol=self._client_protocol,
                        message=str(cancellation_error),
                        error_type=cancellation_error.error_type,
                        status_code=cancellation_error.status_code,
                    ),
                    "more_body": False,
                }
            )

    async def _finalize(self, background: BackgroundTask | None) -> None:
        with anyio.CancelScope(shield=True):
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
                    if background is not None:
                        await background()


async def stream_upstream_iterator(
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
                if capture.capture_body and not capture.is_response_content_truncated:
                    capture_stream_content(
                        capture, capture.content_decoder.decode(forwarded_chunk)
                    )
                yield forwarded_chunk
            if terminal_prefix_length is not None:
                break
    except GatewayTimeoutError as exc:
        record_stream_error(
            capture,
            str(exc),
            status_code=504,
            category=ErrorCategory.TIMEOUT,
        )
        raise
    except httpx.HTTPError as exc:
        record_stream_error(
            capture,
            f"stream failed: {type(exc).__name__}: {exc}",
            status_code=502,
            category=ErrorCategory.NETWORK,
        )
        raise


async def _next_stream_chunk(
    iterator: AsyncIterator[bytes],
    deadline: RequestDeadline,
    *,
    has_seen_first_chunk: bool,
) -> bytes:
    wait = deadline.stream_chunk_wait_seconds(has_seen_first_chunk=has_seen_first_chunk)
    kind = "stream_idle" if has_seen_first_chunk else "first_token"
    async with gateway_timeout_scope(
        wait,
        timeout_message=deadline.timeout_message(kind=kind),
    ):
        return await iterator.__anext__()


async def capture_converted_stream_iterator(
    raw_iterator: AsyncIterator[bytes], capture: StreamCapture
) -> AsyncIterator[bytes]:
    try:
        async for chunk in raw_iterator:
            if (
                capture.capture_body
                and not capture.is_client_response_content_truncated
            ):
                text = capture.client_content_decoder.decode(chunk)
                capture_stream_content(capture, text, client_response=True)
            yield chunk
    except ValueError as exc:
        if not capture.errors:
            record_stream_error(
                capture,
                f"stream conversion failed: {exc}",
                status_code=502,
            )
        raise
