from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_name_parser import extract_request_reasoning_effort

from ....core.runtime_channel_ids import split_runtime_channel_id
from ....models.protocols import ProtocolKind, RequestLogLifecycleStatus


class GatewayKeyPort(Protocol):
    async def adjust_spend(
        self, session: AsyncSession, gateway_key_id: str | None, delta: float
    ) -> None: ...

    async def remarks_by_id(
        self, session: AsyncSession, key_ids: list[str | None]
    ) -> dict[str, str]: ...


class SettingsPort(Protocol):
    async def get_runtime_settings(self) -> dict[str, Any]: ...


RuntimeTimeZone = Callable[[dict[str, Any]], ZoneInfo]


class HydratorPort(Protocol):
    async def hydrate_request_logs(
        self,
        session: AsyncSession,
        entities: list[Any],
        *,
        gateway_has_multiple_keys: bool | None = None,
    ) -> list[Any]: ...

    async def gateway_has_multiple_keys(self, session: AsyncSession) -> bool: ...

    async def request_log_channel_credentials(
        self, session: AsyncSession, channel_ids: list[str | None]
    ) -> tuple[dict[str, int], dict[tuple[str, str], tuple[str, int]]]: ...


def extract_reasoning_effort(request_content: str | None) -> str | None:
    if not request_content:
        return None
    try:
        payload = json.loads(request_content)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return extract_request_reasoning_effort(payload)


REQUEST_LOG_RUNNING_STATUSES = (
    RequestLogLifecycleStatus.CONNECTING.value,
    RequestLogLifecycleStatus.STREAMING.value,
)
REQUEST_LOG_HEALTH_STATUSES = (
    RequestLogLifecycleStatus.SUCCEEDED.value,
    RequestLogLifecycleStatus.FAILED.value,
)
REQUEST_LOG_TERMINAL_STATUSES = (
    *REQUEST_LOG_HEALTH_STATUSES,
    RequestLogLifecycleStatus.CANCELLED.value,
)
REQUEST_LOG_MODEL_FAMILY_PREFIXES: dict[str, tuple[str, ...]] = {
    "openai": ("gpt-", "o1", "o3", "o4", "chatgpt", "openai", "text-embedding"),
    "claude": ("claude", "anthropic"),
    "gemini": ("gemini", "gemma", "google"),
    "deepseek": ("deepseek",),
    "qwen": ("qwen", "qwq", "alibaba"),
    "kimi": ("moonshot", "kimi"),
    "glm": ("glm", "chatglm", "zhipu", "z-ai", "zai-"),
    "minimax": ("minimax", "abab", "minmax"),
}


def group_channel_ids_by_protocol_config(
    channel_ids: Iterable[str | None],
) -> tuple[dict[str, list[str]], dict[str, ProtocolKind]]:
    """Group runtime channel IDs by protocol configuration."""
    channels_by_protocol_config: dict[str, list[str]] = {}
    protocol_by_channel_id: dict[str, ProtocolKind] = {}
    seen_channel_ids: set[str] = set()

    for raw_channel_id in channel_ids:
        channel_id = raw_channel_id.strip() if isinstance(raw_channel_id, str) else ""
        if not channel_id or channel_id in seen_channel_ids:
            continue
        seen_channel_ids.add(channel_id)

        parsed = split_runtime_channel_id(channel_id)
        protocol_config_id = parsed[0] if parsed is not None else channel_id
        if parsed is not None:
            protocol_by_channel_id[channel_id] = parsed[1]
        channels_by_protocol_config.setdefault(protocol_config_id, []).append(
            channel_id
        )

    return channels_by_protocol_config, protocol_by_channel_id
