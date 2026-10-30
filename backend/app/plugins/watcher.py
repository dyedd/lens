"""轮询插件目录，文件有变化时触发与手动重载相同的流程。"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from .discovery import DirectoryStamp, build_directory_stamp

ReloadCallback = Callable[[], Awaitable[object]]


class PluginDirectoryWatcher:
    """每隔 `poll_seconds` 比较一次目录戳；出错只记录，继续轮询。"""

    def __init__(
        self,
        root: Path,
        *,
        on_change: ReloadCallback,
        logger: logging.Logger,
        poll_seconds: float = 2.0,
    ) -> None:
        self._root = root
        self._on_change = on_change
        self._logger = logger
        self._poll_seconds = poll_seconds
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        stamp = await asyncio.to_thread(self._build_stamp)
        self._task = asyncio.create_task(self._watch(stamp))

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    def _build_stamp(self) -> DirectoryStamp:
        if not self._root.is_dir():
            return ()
        return build_directory_stamp(self._root)

    async def _watch(self, stamp: DirectoryStamp) -> None:
        while True:
            await asyncio.sleep(self._poll_seconds)
            try:
                current = await asyncio.to_thread(self._build_stamp)
            except OSError:
                self._logger.warning("Plugin directory scan failed", exc_info=True)
                continue
            if current == stamp:
                continue
            # 先记下新戳：重载失败时等文件再变或手动重载，不每轮重试。
            stamp = current
            try:
                await self._on_change()
            except Exception:
                self._logger.exception("Plugin hot reload failed")
