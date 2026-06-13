from __future__ import annotations

from .runtime_context import (
    Any,
    AsyncIterator,
    ChannelConfig,
    Mapping,
    ProtocolKind,
    RouteTarget,
    RoutingPlan,
    UpstreamRequestError,
    _RequestDeadline,
    app_state,
    asynccontextmanager,
    asyncio,
    can_reach_protocol,
    deepcopy,
    json,
    perf_counter,
    urlsplit,
)


async def _resolve_routing_plan(
    protocol: ProtocolKind, requested_model: str, channels: list[ChannelConfig]
) -> RoutingPlan:
    matched_group = await app_state.group_repo.find_group_by_name(
        protocol.value, requested_model
    )
    if matched_group is not None and protocol in matched_group.protocols:
        resolved_group = matched_group
        if matched_group.route_group_id.strip():
            try:
                resolved_group = await app_state.group_repo.get_group(
                    matched_group.route_group_id
                )
            except KeyError as exc:
                raise LookupError(
                    f"Route target model group not found: {matched_group.route_group_id}"
                ) from exc
            if resolved_group.route_group_id.strip():
                raise LookupError(
                    f"Route target must be an execution group: {resolved_group.name}"
                )
            if protocol not in resolved_group.protocols:
                raise LookupError(f"No model group matched {requested_model}")
        channel_map = {channel.id: channel for channel in channels}
        route_targets = [
            RouteTarget(
                channel=channel_map[item.channel_id],
                model_name=item.model_name,
                credential_id=item.credential_id,
                credential_name=item.credential_name or None,
            )
            for item in resolved_group.items
            if item.enabled
            and item.channel_id in channel_map
            and can_reach_protocol(channel_map[item.channel_id].protocol, protocol)
        ]
        return RoutingPlan(
            requested_group_name=matched_group.name,
            resolved_group_name=resolved_group.name,
            requested_group=matched_group,
            resolved_group=resolved_group,
            strategy=resolved_group.strategy,
            route_targets=route_targets,
            use_model_matching=False,
            cursor_key=f"{protocol.value}:{resolved_group.id}",
        )

    raise LookupError(f"No model group matched {requested_model}")


def _prepare_upstream_body(
    protocol: ProtocolKind, body: dict[str, Any], target_model_name: str | None
) -> dict[str, Any]:
    payload = deepcopy(body)
    if protocol == ProtocolKind.OPENAI_RESPONSES and "input" in payload:
        payload["input"] = _normalize_openai_responses_input(payload.get("input"))
    if not target_model_name:
        return payload
    payload["model"] = target_model_name
    return payload


def _clean_reasoning_effort(value: Any) -> str | None:
    if isinstance(value, int) and value > 0:
        return str(value)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 32:
        return None
    if any(char.isspace() for char in normalized):
        return None
    return normalized


def _extract_request_reasoning_effort(*bodies: Mapping[str, Any] | None) -> str | None:
    for body in bodies:
        if not isinstance(body, Mapping):
            continue

        for key in (
            "reasoning_effort",
            "reasoningEffort",
            "model_reasoning_effort",
            "modelReasoningEffort",
            "effort",
            "effortLevel",
        ):
            effort = _clean_reasoning_effort(body.get(key))
            if effort:
                return effort

        reasoning = body.get("reasoning")
        if isinstance(reasoning, Mapping):
            effort = _clean_reasoning_effort(reasoning.get("effort"))
            if effort:
                return effort
        else:
            effort = _clean_reasoning_effort(reasoning)
            if effort:
                return effort

        thinking = body.get("thinking")
        if isinstance(thinking, Mapping):
            for key in ("effort", "budget_tokens"):
                effort = _clean_reasoning_effort(thinking.get(key))
                if effort:
                    return effort

        output_config = body.get("output_config")
        if isinstance(output_config, Mapping):
            effort = _clean_reasoning_effort(output_config.get("effort"))
            if effort:
                return effort

        extra_body = body.get("extra_body")
        if isinstance(extra_body, Mapping):
            effort = _extract_request_reasoning_effort(extra_body)
            if effort:
                return effort

    return None


def _apply_deepseek_thinking_compat(
    channel: ChannelConfig, body: dict[str, Any]
) -> dict[str, Any]:
    if not _is_deepseek_thinking_target(channel, body.get("model")):
        return body
    if _is_thinking_disabled(body):
        return body
    if channel.protocol == ProtocolKind.ANTHROPIC:
        return _apply_deepseek_anthropic_thinking_compat(body)
    if channel.protocol == ProtocolKind.OPENAI_CHAT:
        return _apply_deepseek_chat_reasoning_compat(body)
    return body


def _is_deepseek_thinking_target(channel: ChannelConfig, model_name: Any) -> bool:
    return _is_deepseek_base_url(str(channel.base_url)) or _is_deepseek_model_name(
        model_name
    )


def _is_deepseek_base_url(base_url: str) -> bool:
    host = (urlsplit(base_url).hostname or "").lower()
    return host == "api.deepseek.com"


def _is_deepseek_model_name(model_name: Any) -> bool:
    if not isinstance(model_name, str):
        return False
    normalized = model_name.lower()
    return "deepseek-v4" in normalized or "deepseek-reasoner" in normalized


def _is_thinking_disabled(body: dict[str, Any]) -> bool:
    thinking = body.get("thinking")
    if not isinstance(thinking, dict):
        return False
    return str(thinking.get("type") or "").lower() == "disabled"


def _apply_deepseek_anthropic_thinking_compat(body: dict[str, Any]) -> dict[str, Any]:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return body

    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        if not _anthropic_content_has_tool_use(content):
            continue
        if _anthropic_content_has_thinking(content):
            continue
        content.insert(0, {"type": "thinking", "thinking": ""})
    return body


def _anthropic_content_has_tool_use(content: list[Any]) -> bool:
    return any(
        isinstance(block, dict) and block.get("type") == "tool_use" for block in content
    )


def _anthropic_content_has_thinking(content: list[Any]) -> bool:
    return any(
        isinstance(block, dict) and block.get("type") == "thinking" for block in content
    )


def _apply_deepseek_chat_reasoning_compat(body: dict[str, Any]) -> dict[str, Any]:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return body

    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        if not message.get("tool_calls"):
            continue
        if message.get("reasoning_content") is None:
            message["reasoning_content"] = ""
    return body


def _apply_param_override(
    channel: ChannelConfig, body: dict[str, Any]
) -> dict[str, Any]:
    raw_override = channel.param_override.strip()
    if not raw_override:
        return body

    try:
        override = json.loads(raw_override)
    except json.JSONDecodeError as exc:
        raise UpstreamRequestError(
            status_code=400,
            detail=(
                f"Invalid param override JSON for channel {channel.name}: "
                f"{exc.msg} at line {exc.lineno} column {exc.colno}"
            ),
            router_status_code=None,
        ) from exc

    if not isinstance(override, dict):
        raise UpstreamRequestError(
            status_code=400,
            detail=(
                f"Invalid param override for channel {channel.name}: "
                "expected a JSON object"
            ),
            router_status_code=None,
        )
    if "model" in override:
        raise UpstreamRequestError(
            status_code=400,
            detail=(
                f"Invalid param override for channel {channel.name}: "
                "model cannot be overridden"
            ),
            router_status_code=None,
        )

    return _deep_merge_json_objects(body, override)


def _deep_merge_json_objects(
    base: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, override_value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            merged[key] = _deep_merge_json_objects(base_value, override_value)
        else:
            merged[key] = deepcopy(override_value)
    return merged


def _normalize_openai_responses_input(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        return [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            }
        ]

    if isinstance(value, list):
        normalized_items: list[Any] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                normalized_items.append(
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": text}],
                    }
                )
                continue

            if isinstance(item, dict) and isinstance(item.get("content"), str):
                normalized = dict(item)
                normalized["content"] = [
                    {"type": "input_text", "text": item["content"]}
                ]
                normalized_items.append(normalized)
                continue

            normalized_items.append(item)
        return normalized_items

    return value


def _elapsed_ms(started_at: float) -> int:
    return max(int((perf_counter() - started_at) * 1000), 0)


@asynccontextmanager
async def _deadline_scope(
    deadline: _RequestDeadline,
) -> AsyncIterator[None]:
    remaining = deadline.remaining_seconds()
    if remaining is None:
        yield
        return
    if remaining <= 0:
        raise TimeoutError(deadline.message())
    async with asyncio.timeout(remaining):
        yield


def _request_body_too_large_message(size: int, limit: int) -> str | None:
    normalized_limit = max(int(limit), 0)
    if normalized_limit <= 0 or size <= normalized_limit:
        return None
    return (
        f"Request body is {size} bytes, exceeds Lens limit "
        f"{normalized_limit} bytes. Split the context or increase "
        "LENS_MAX_REQUEST_BODY_BYTES."
    )


def _final_upstream_failure(
    errors: list[str], failure_status_codes: list[int | None]
) -> tuple[int, str, str]:
    for error, status_code in zip(errors, failure_status_codes, strict=False):
        if _is_request_too_large_error(status_code, error):
            return 413, "request_too_large", error
    if failure_status_codes and all(
        status_code == 504 for status_code in failure_status_codes
    ):
        return 504, "gateway_timeout", "All upstream channels timed out"
    return 502, "upstream_error", "All upstream channels failed"


def _is_request_too_large_error(status_code: int | None, message: str) -> bool:
    if status_code != 413:
        return False
    normalized = message.lower()
    return (
        "request body exceeds" in normalized
        or "request_too_large" in normalized
        or "too large" in normalized
        or "exceeds lens limit" in normalized
    )
