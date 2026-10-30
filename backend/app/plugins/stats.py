"""插件扩展点的调用统计，以及限流后的失败日志。"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass

from ..models.plugins import PluginExtensionStatsView

logger = logging.getLogger(__name__)

# 计入失败次数的调用结果。
FAILURE_OUTCOMES = frozenset({"timeout", "error", "invalid"})
_LOG_LINES_PER_MINUTE = 60
_LOG_DETAIL_LIMIT = 2000


@dataclass(slots=True)
class _ExtensionStats:
    calls: int = 0
    failures: int = 0
    total_ms: float = 0.0
    last_outcome: str = ""
    last_error: str = ""
    dropped: int = 0


class PluginStats:
    """按插件与扩展点累计调用次数、失败、耗时与最近一次结果。"""

    def __init__(self) -> None:
        self._stats: dict[tuple[str, str], _ExtensionStats] = {}
        self._log_times: dict[str, deque[float]] = {}

    def record(
        self,
        plugin_id: str,
        extension: str,
        *,
        outcome: str,
        elapsed_ms: float,
        error: BaseException | None = None,
    ) -> None:
        """记一次调用；失败时更新最近错误并写限流日志。"""
        stats = self._entry(plugin_id, extension)
        stats.calls += 1
        stats.total_ms += max(elapsed_ms, 0.0)
        stats.last_outcome = outcome
        if outcome not in FAILURE_OUTCOMES:
            return
        stats.failures += 1
        stats.last_error = _describe_failure(outcome, error)
        self._log_failure(plugin_id, extension, stats.last_error, error)

    def record_dropped(self, plugin_id: str, extension: str) -> None:
        """记一次因队列已满而丢弃的投递。"""
        self._entry(plugin_id, extension).dropped += 1

    def views(self, plugin_id: str) -> list[PluginExtensionStatsView]:
        return [
            PluginExtensionStatsView(
                extension=extension,
                calls=stats.calls,
                failures=stats.failures,
                avg_ms=round(stats.total_ms / stats.calls, 3) if stats.calls else 0.0,
                last_outcome=stats.last_outcome,
                last_error=stats.last_error,
                dropped=stats.dropped,
            )
            for (owner, extension), stats in sorted(self._stats.items())
            if owner == plugin_id
        ]

    def _entry(self, plugin_id: str, extension: str) -> _ExtensionStats:
        key = (plugin_id, extension)
        stats = self._stats.get(key)
        if stats is None:
            stats = self._stats[key] = _ExtensionStats()
        return stats

    def _log_failure(
        self,
        plugin_id: str,
        extension: str,
        detail: str,
        error: BaseException | None,
    ) -> None:
        now = time.monotonic()
        times = self._log_times.setdefault(plugin_id, deque())
        while times and now - times[0] >= 60:
            times.popleft()
        if len(times) >= _LOG_LINES_PER_MINUTE:
            return
        times.append(now)
        logger.warning(
            "Plugin %s %s failed: %s",
            plugin_id,
            extension,
            detail,
            exc_info=error if isinstance(error, Exception) else None,
        )


def _describe_failure(outcome: str, error: BaseException | None) -> str:
    if error is None or isinstance(error, TimeoutError):
        return outcome
    message = str(error)
    detail = f"{type(error).__name__}: {message}" if message else type(error).__name__
    return detail[:_LOG_DETAIL_LIMIT]
