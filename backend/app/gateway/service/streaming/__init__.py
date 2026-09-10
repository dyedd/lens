"""Streaming transport, parsing, recovery, and logging primitives."""

from .detect import (
    _mark_stream_first_chunk,
    _record_chat_stream_finish_reasons,
    _record_stream_completion,
    _stream_payload_has_output,
)
from .events import (
    _capture_stream_event_chunk,
    _flush_stream_event_buffer,
)
from .logging import (
    StreamLogOutcome,
    record_stream_request_log,
    safe_estimate_cost,
    stream_log_outcome,
)
from .restore import distill_stream_response_content
from .transport import (
    FinalizingStreamingResponse,
    capture_converted_stream_iterator,
    stream_upstream_iterator,
)
from .types import (
    OPENAI_RESPONSES_TERMINAL_EVENTS,
    AnthropicStreamBlock,
    ChatStreamChoice,
    ChatStreamDelta,
    parse_anthropic_stream_payload,
    parse_chat_stream_payload,
    parse_ndjson_payloads,
    parse_sse_payloads,
    to_lf_line_endings,
)
from .usage import (
    EMPTY_USAGE,
    extract_response_usage,
    extract_stream_usage,
    extract_usage_from_payload,
)

__all__ = [
    "EMPTY_USAGE",
    "OPENAI_RESPONSES_TERMINAL_EVENTS",
    "AnthropicStreamBlock",
    "ChatStreamChoice",
    "ChatStreamDelta",
    "FinalizingStreamingResponse",
    "StreamLogOutcome",
    "capture_converted_stream_iterator",
    "distill_stream_response_content",
    "extract_response_usage",
    "extract_stream_usage",
    "extract_usage_from_payload",
    "parse_anthropic_stream_payload",
    "parse_chat_stream_payload",
    "parse_ndjson_payloads",
    "parse_sse_payloads",
    "record_stream_request_log",
    "safe_estimate_cost",
    "stream_log_outcome",
    "stream_upstream_iterator",
    "to_lf_line_endings",
]
