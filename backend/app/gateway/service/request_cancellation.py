from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import anyio

from ...core.errors import RequestCancelledError


@dataclass(slots=True)
class RequestCancellation:
    is_cancelled: bool = False
    _scope: anyio.CancelScope | None = None

    def cancel(self) -> None:
        self.is_cancelled = True
        if self._scope is not None:
            self._scope.cancel()

    @contextmanager
    def watch(self) -> Iterator[None]:
        # 只中断上游传输和等待；日志写入在作用域外完成。
        if self.is_cancelled:
            raise RequestCancelledError()
        with anyio.CancelScope() as scope:
            self._scope = scope
            try:
                yield
            finally:
                self._scope = None
        if self.is_cancelled:
            raise RequestCancelledError()
