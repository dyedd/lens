from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ....models.channels import ChannelConfig
from ....models.protocols import RequestLogLifecycleStatus
from ....persistence.repositories.model_price_repository import ModelCostEstimate
from ..app_state import app_state, logger
from ..request_logger import _RequestLogger, _update_request_log
from ..routing_plan import _elapsed_ms
from ..runtime_types import (
    StreamCapture,
    UpstreamResult,
    _record_stream_parse_error,
)
from .stream_events import _join_stream_chunks, _stream_capture_usage
from .stream_restore import _distill_stream_response_content
from .usage import (
    _describe_stream_capture_issue,
    _extract_stream_usage,
    _is_pure_client_stream_disconnect,
    _is_stream_body_cut_short,
)


async def _safe_estimate_cost(
    model_name: str | None,
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int = 0,
    cache_write_input_tokens: int = 0,
    image_count: int = 0,
    rate_multiplier: float | None = None,
) -> ModelCostEstimate:
    try:
        return await app_state.model_price_repo.estimate_model_cost(
            model_name,
            input_tokens,
            output_tokens,
            cache_read_input_tokens,
            cache_write_input_tokens,
            image_count,
            rate_multiplier,
        )
    except Exception:
        logger.exception("Failed to estimate model cost")
        return ModelCostEstimate()


@dataclass(frozen=True, slots=True)
class StreamLogOutcome:
    """Terminal stream state shared by route-health reporting and log finalization."""

    lifecycle_status: RequestLogLifecycleStatus
    capture_issue: str | None
    status_code: int


def _stream_log_outcome(
    result: UpstreamResult, capture: StreamCapture | None
) -> StreamLogOutcome:
    capture_issue = _describe_stream_capture_issue(capture)
    return StreamLogOutcome(
        lifecycle_status=_stream_log_lifecycle_status(capture, capture_issue),
        capture_issue=capture_issue,
        status_code=_stream_log_status_code(result, capture, capture_issue),
    )


async def _record_stream_request_log(
    *,
    log_ctx: _RequestLogger,
    channel: ChannelConfig,
    result: UpstreamResult,
    attempts: list[dict[str, Any]],
    outcome: StreamLogOutcome,
) -> None:
    capture = result.stream_capture
    if capture is not None and capture.first_token_update_task is not None:
        await capture.first_token_update_task
    raw_content = (
        _join_stream_chunks(capture.response_content_chunks)
        if capture is not None and capture.capture_body
        else result.response_content
    )
    if capture is not None:
        capture.response_content_chunks.clear()
    response_protocol = channel.protocol
    response_raw_content = raw_content
    client_response_content = (
        _join_stream_chunks(capture.client_response_content_chunks)
        if capture is not None and capture.capture_body
        else None
    )
    if capture is not None:
        capture.client_response_content_chunks.clear()
    if (
        capture is not None
        and log_ctx.protocol != channel.protocol
        and client_response_content
    ):
        response_protocol = log_ctx.protocol
        response_raw_content = client_response_content
    parse_errors: list[str] = []
    # A body that ends mid-frame (client hung up, or capture hit its size cap) would
    # only yield bogus parse errors if it were re-parsed as one document.
    upstream_body_incomplete = _is_stream_body_cut_short(capture) or (
        capture is not None and capture.is_response_content_truncated
    )
    logged_body_incomplete = upstream_body_incomplete or (
        capture is not None and capture.is_client_response_content_truncated
    )
    if raw_content and not upstream_body_incomplete:
        try:
            parsed = _extract_stream_usage(
                channel.protocol, raw_content, parse_errors=parse_errors
            )
        except ValueError as exc:
            parse_errors.append(str(exc))
            parsed = _stream_capture_usage(capture)
    else:
        parsed = _stream_capture_usage(capture)
    if capture is not None:
        for error in parse_errors:
            _record_stream_parse_error(capture, error)
    try:
        if logged_body_incomplete:
            distilled_content = response_raw_content
        else:
            distilled_content = _distill_stream_response_content(
                response_protocol, response_raw_content
            )
    except ValueError as exc:
        if capture is not None:
            _record_stream_parse_error(capture, str(exc))
        distilled_content = response_raw_content
    first_token_latency_ms = (
        capture.first_token_latency_ms
        if capture is not None
        else result.first_token_latency_ms
    )
    latency_ms = _elapsed_ms(log_ctx.started_at)
    status_code = outcome.status_code
    attempt_logs = [dict(item) for item in attempts]
    if attempt_logs and attempt_logs[-1].get("success"):
        # Prefer full stream duration for attempt timing; first-token is tracked separately.
        attempt_logs[-1]["duration_ms"] = latency_ms
        if outcome.capture_issue is not None:
            attempt_logs[-1]["success"] = False
            attempt_logs[-1]["error_message"] = outcome.capture_issue
            if status_code != result.status_code:
                attempt_logs[-1]["status_code"] = status_code
    cost = await _safe_estimate_cost(
        log_ctx.resolved_group_name,
        parsed["input_tokens"],
        parsed["output_tokens"],
        parsed["cache_read_input_tokens"],
        parsed["cache_write_input_tokens"],
        rate_multiplier=log_ctx.rate_multiplier,
    )
    await _update_request_log(
        log_ctx.request_log_id,
        protocol=log_ctx.protocol,
        requested_group_name=log_ctx.requested_group_name,
        resolved_group_name=log_ctx.resolved_group_name,
        upstream_model_name=parsed["resolved_model"] or result.upstream_model_name,
        channel_id=channel.id,
        channel_name=channel.name,
        gateway_key=log_ctx.gateway_key,
        user_agent=log_ctx.user_agent,
        lifecycle_status=outcome.lifecycle_status,
        status_code=status_code,
        success=outcome.lifecycle_status == RequestLogLifecycleStatus.SUCCEEDED,
        is_stream=True,
        first_token_latency_ms=first_token_latency_ms,
        latency_ms=latency_ms,
        input_tokens=parsed["input_tokens"],
        cache_read_input_tokens=parsed["cache_read_input_tokens"],
        cache_write_input_tokens=parsed["cache_write_input_tokens"],
        output_tokens=parsed["output_tokens"],
        total_tokens=parsed["total_tokens"],
        input_cost_usd=cost.input_cost_usd,
        output_cost_usd=cost.output_cost_usd,
        total_cost_usd=cost.total_cost_usd,
        rate_multiplier=log_ctx.rate_multiplier,
        billing_mode=cost.billing_mode,
        billing_units=cost.billing_units,
        request_content=result.request_content,
        response_content=distilled_content,
        attempts=attempt_logs,
        error_message=outcome.capture_issue,
    )


def _stream_log_lifecycle_status(
    capture: StreamCapture | None, capture_issue: str | None
) -> RequestLogLifecycleStatus:
    if _is_pure_client_stream_disconnect(capture):
        return RequestLogLifecycleStatus.CANCELLED
    if capture_issue is not None:
        return RequestLogLifecycleStatus.FAILED
    return RequestLogLifecycleStatus.SUCCEEDED


def _stream_log_status_code(
    result: UpstreamResult, capture: StreamCapture | None, capture_issue: str | None
) -> int:
    if capture_issue is None:
        return result.status_code
    if capture is not None and capture.error_status_code is not None:
        return capture.error_status_code
    return result.status_code
