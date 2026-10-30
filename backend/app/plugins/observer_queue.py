"""把已完成请求的摘要排队交给观察者，不占用请求本身的时间。"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Sequence

from .contract import EXT_REQUEST_OBSERVER, PluginHook, RequestObserver, RequestRecord
from .stats import PluginStats

_QUEUE_SIZE = 1024
_OBSERVER_TIMEOUT_SECONDS = 0.25
# 关闭时最多等这么久把已排队的摘要交完，剩下的丢弃。
_DRAIN_TIMEOUT_SECONDS = 1.0

_Delivery = tuple[RequestRecord, tuple[PluginHook[RequestObserver], ...]]


class ObserverQueue:
    """有界队列加一个后台 worker；队列满时丢弃并计数。"""

    def __init__(self, stats: PluginStats) -> None:
        self._stats = stats
        self._queue: asyncio.Queue[_Delivery] | None = None
        self._worker: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def submit(
        self,
        record: RequestRecord,
        observers: Sequence[PluginHook[RequestObserver]],
    ) -> None:
        if not observers:
            return
        queue = self._ensure_worker()
        try:
            queue.put_nowait((record, tuple(observers)))
        except asyncio.QueueFull:
            for observer in observers:
                self._stats.record_dropped(observer.plugin_id, EXT_REQUEST_OBSERVER)

    async def aclose(self) -> None:
        """交完已排队的摘要（有时限），然后停止 worker。"""
        worker, queue, loop = self._worker, self._queue, self._loop
        self._worker = self._queue = self._loop = None
        if worker is None or queue is None or worker.done():
            return
        if loop is not asyncio.get_running_loop():
            # worker 属于已结束的事件循环，无法在这里等待。
            return
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(queue.join(), _DRAIN_TIMEOUT_SECONDS)
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker

    def _ensure_worker(self) -> asyncio.Queue[_Delivery]:
        loop = asyncio.get_running_loop()
        if (
            self._queue is None
            or self._worker is None
            or self._worker.done()
            or self._loop is not loop
        ):
            # 事件循环换了（测试每次新开循环）就连队列一起重建。
            self._loop = loop
            self._queue = asyncio.Queue(maxsize=_QUEUE_SIZE)
            self._worker = loop.create_task(self._run(self._queue))
        return self._queue

    async def _run(self, queue: asyncio.Queue[_Delivery]) -> None:
        while True:
            record, observers = await queue.get()
            try:
                for observer in observers:
                    await self._deliver(observer, record)
            finally:
                queue.task_done()

    async def _deliver(
        self, observer: PluginHook[RequestObserver], record: RequestRecord
    ) -> None:
        started = time.perf_counter()
        error: BaseException | None = None
        try:
            async with asyncio.timeout(_OBSERVER_TIMEOUT_SECONDS):
                await observer.hook.completed(record)
        except TimeoutError as exc:
            outcome, error = "timeout", exc
        except Exception as exc:
            outcome, error = "error", exc
        else:
            outcome = "ok"
        self._stats.record(
            observer.plugin_id,
            EXT_REQUEST_OBSERVER,
            outcome=outcome,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            error=error,
        )
