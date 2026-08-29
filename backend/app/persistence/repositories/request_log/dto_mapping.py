from __future__ import annotations

import json
from datetime import UTC
from typing import Any

from app.models.protocols import RequestLogLifecycleStatus
from app.models.request_logs import RequestLogAttempt, RequestLogDetail, RequestLogItem
from app.persistence.entities import RequestLogEntity

from .reasoning_effort import clean_reasoning_effort, extract_reasoning_effort


def primary_attempt(
    attempts: list[dict[str, Any]], channel_id: str | None
) -> dict[str, Any]:
    if channel_id:
        for attempt in reversed(attempts):
            if str(attempt.get("channel_id") or "") == channel_id:
                return attempt
        return {}
    return attempts[-1] if attempts else {}


def credential_values(
    channel_id: str | None,
    credential_id: Any,
    credential_name: Any,
    credential_metadata: dict[tuple[str, str], tuple[str, int]],
) -> tuple[str | None, str, int]:
    gateway_key_id = credential_id.strip() if isinstance(credential_id, str) else None
    snapshot_name = credential_name.strip() if isinstance(credential_name, str) else ""
    current = credential_metadata.get(
        ((channel_id or "").strip(), gateway_key_id or "")
    )
    if current is None:
        return gateway_key_id, snapshot_name, 0
    current_name, current_number = current
    return gateway_key_id, current_name.strip(), current_number


def to_request_log(
    entity: RequestLogEntity,
    *,
    gateway_key_remark: str | None = None,
    gateway_has_multiple_keys: bool = False,
    channel_has_multiple_credentials: bool = False,
    credential_metadata: dict[tuple[str, str], tuple[str, int]] | None = None,
) -> RequestLogItem:
    attempts = parse_attempts_json(entity.attempts_json)
    primary = primary_attempt(attempts, entity.channel_id)
    credential_id, credential_name, credential_number = credential_values(
        entity.channel_id,
        primary.get("credential_id"),
        primary.get("credential_name"),
        credential_metadata or {},
    )
    reasoning_effort = extract_reasoning_effort(
        entity.request_content
    ) or clean_reasoning_effort(primary.get("reasoning_effort"))
    return RequestLogItem(
        id=entity.id,
        protocol=entity.protocol,
        user_agent=entity.user_agent,
        requested_group_name=entity.requested_group_name,
        resolved_group_name=entity.resolved_group_name,
        upstream_model_name=entity.upstream_model_name,
        channel_id=entity.channel_id,
        channel_name=entity.channel_name,
        credential_id=credential_id,
        credential_name=credential_name,
        credential_number=credential_number,
        channel_has_multiple_credentials=channel_has_multiple_credentials,
        gateway_key_id=entity.gateway_key_id,
        gateway_key_remark=gateway_key_remark or None,
        gateway_has_multiple_keys=gateway_has_multiple_keys,
        reasoning_effort=reasoning_effort,
        status_code=entity.status_code,
        success=bool(entity.success),
        lifecycle_status=(
            RequestLogLifecycleStatus(entity.lifecycle_status)
            if entity.lifecycle_status in RequestLogLifecycleStatus._value2member_map_
            else (
                RequestLogLifecycleStatus.SUCCEEDED
                if entity.success
                else RequestLogLifecycleStatus.FAILED
            )
        ),
        is_stream=bool(entity.is_stream),
        first_token_latency_ms=entity.first_token_latency_ms,
        latency_ms=entity.latency_ms,
        input_tokens=entity.input_tokens,
        cache_read_input_tokens=entity.cache_read_input_tokens,
        cache_write_input_tokens=entity.cache_write_input_tokens,
        output_tokens=entity.output_tokens,
        total_tokens=entity.total_tokens,
        input_cost_usd=entity.input_cost_usd,
        output_cost_usd=entity.output_cost_usd,
        total_cost_usd=entity.total_cost_usd,
        rate_multiplier=entity.rate_multiplier,
        billing_mode=entity.billing_mode,
        billing_units=entity.billing_units,
        attempt_count=len(attempts),
        error_message=entity.error_message,
        created_at=entity.created_at.replace(tzinfo=UTC).isoformat(),
    )


def to_request_log_attempt(
    item: dict[str, Any],
    credential_metadata: dict[tuple[str, str], tuple[str, int]],
    channel_credential_counts: dict[str, int],
) -> RequestLogAttempt:
    payload = dict(item)
    credential_id, credential_name, credential_number = credential_values(
        str(item.get("channel_id") or ""),
        item.get("credential_id"),
        item.get("credential_name"),
        credential_metadata,
    )
    payload["credential_id"] = credential_id
    payload["credential_name"] = credential_name
    payload["credential_number"] = credential_number
    payload["channel_has_multiple_credentials"] = (
        channel_credential_counts.get(str(item.get("channel_id") or ""), 0) > 1
    )
    return RequestLogAttempt(**payload)


def to_request_log_detail(
    entity: RequestLogEntity,
    *,
    gateway_key_remark: str | None = None,
    gateway_has_multiple_keys: bool = False,
    channel_has_multiple_credentials: bool = False,
    credential_metadata: dict[tuple[str, str], tuple[str, int]] | None = None,
    channel_credential_counts: dict[str, int] | None = None,
) -> RequestLogDetail:
    resolved_metadata = credential_metadata or {}
    resolved_counts = channel_credential_counts or {}
    return RequestLogDetail(
        **to_request_log(
            entity,
            gateway_key_remark=gateway_key_remark,
            gateway_has_multiple_keys=gateway_has_multiple_keys,
            channel_has_multiple_credentials=channel_has_multiple_credentials,
            credential_metadata=resolved_metadata,
        ).model_dump(),
        request_content=entity.request_content,
        response_content=entity.response_content,
        attempts=[
            to_request_log_attempt(item, resolved_metadata, resolved_counts)
            for item in parse_attempts_json(entity.attempts_json)
        ],
    )


def parse_attempts_json(raw_value: str | None) -> list[dict[str, Any]]:
    if not raw_value:
        return []
    payload = json.loads(raw_value)
    if not isinstance(payload, list) or not all(
        isinstance(item, dict) for item in payload
    ):
        raise ValueError("Invalid request log attempts JSON")
    return payload
