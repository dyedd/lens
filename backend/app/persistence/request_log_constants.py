from __future__ import annotations

from ..models.protocols import RequestLogLifecycleStatus

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
