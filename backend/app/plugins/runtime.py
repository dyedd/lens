"""按约定的时限、顺序与失败策略调度插件扩展点，并记录调用统计。

网关只经由这里调用插件。所有扩展点都 fail open：插件出错、超时或返回非法值只记统计，
请求照常继续；只有 request_rewrite 抛出的 `PluginRejection` 会拒绝请求。
"""

from __future__ import annotations

import asyncio
import json
import operator
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, replace
from time import perf_counter
from typing import TYPE_CHECKING, Any

import httpx

from .contract import (
    DROP_EVENT,
    EXT_REQUEST_REWRITE,
    EXT_RESPONSE_EVENT,
    EXT_ROUTE_STRATEGY,
    EXT_UPSTREAM_CREDENTIAL,
    EXT_UPSTREAM_REQUEST,
    EXT_UPSTREAM_RESPONSE,
    HookContext,
    InboundRequest,
    PluginHook,
    PluginHookSet,
    PluginRejection,
    RequestRecord,
    RequestRewriteHook,
    ResponseEvent,
    ResponseEventHook,
    ResponseHook,
    RouteSeat,
    UpstreamCall,
    UpstreamHook,
    UpstreamResponse,
)
from .stream_events import NdjsonEventSplitter, SseEventSplitter, SseJsonEvent

if TYPE_CHECKING:
    from .stats import PluginStats

_REWRITE_TIMEOUT_SECONDS = 0.25
_CREDENTIAL_TIMEOUT_SECONDS = 15.0
_UPSTREAM_REQUEST_TIMEOUT_SECONDS = 0.25
_RESPONSE_TIMEOUT_SECONDS = 0.25
_EVENT_TIMEOUT_SECONDS = 0.05
_STRATEGY_LIMIT_MS = 20.0
_HEADER_NAME_PATTERN = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")


class PluginRun:
    """一次请求的插件状态：扩展点快照与各插件的私有 state。"""

    def __init__(self, hooks: PluginHookSet, request: InboundRequest) -> None:
        self.hooks = hooks
        # 改写后由调用方用 dataclasses.replace 换成新的事实。
        self.request = request
        self._states: dict[str, dict[str, Any]] = {}
        self._is_finished = False
        self._is_closed = False
        for lifetime in hooks.lifetimes.values():
            lifetime.acquire()

    def close(self) -> None:
        if self._is_closed:
            return
        self._is_closed = True
        for lifetime in self.hooks.lifetimes.values():
            lifetime.release()

    def context_for(self, plugin_id: str) -> HookContext:
        """同一插件在本次请求里的各个钩子共享同一个 state。"""
        state = self._states.setdefault(plugin_id, {})
        return HookContext(self.request, state)


def begin_run(hooks: PluginHookSet, request: InboundRequest) -> PluginRun:
    """请求开始时取一份扩展点快照；之后的插件重载不影响这次请求。"""
    return PluginRun(hooks, request)


def system_run(hooks: PluginHookSet, protocol: str) -> PluginRun:
    """网关自己发起的请求（模型发现、探测等）用的插件状态。"""
    request = InboundRequest(protocol=protocol, path="", model="", is_stream=False)
    return PluginRun(hooks, request)


@dataclass(frozen=True, slots=True)
class _HookCall:
    outcome: str  # ok / timeout / error
    value: Any
    error: BaseException | None
    elapsed_ms: float


async def _call_hook(seconds: float, invoke: Callable[[], Awaitable[Any]]) -> _HookCall:
    """在时限内调用插件，超时与异常都收成结果；取消照常向外传播。"""
    started_at = perf_counter()
    try:
        async with asyncio.timeout(seconds):
            value = await invoke()
    except TimeoutError:
        return _HookCall("timeout", None, None, _elapsed_ms(started_at))
    except Exception as exc:
        return _HookCall("error", None, exc, _elapsed_ms(started_at))
    return _HookCall("ok", value, None, _elapsed_ms(started_at))


def _record_call(
    stats: PluginStats, plugin_id: str, extension: str, called: _HookCall
) -> None:
    stats.record(
        plugin_id,
        extension,
        outcome=called.outcome,
        elapsed_ms=called.elapsed_ms,
        error=called.error,
    )


def _matches(
    stats: PluginStats, plugin_id: str, extension: str, hook: Any, target: Any
) -> bool:
    """`matches` 抛异常记为 error，并跳过这个钩子。"""
    started_at = perf_counter()
    try:
        return bool(hook.matches(target))
    except Exception as exc:
        stats.record(
            plugin_id,
            extension,
            outcome="error",
            elapsed_ms=_elapsed_ms(started_at),
            error=exc,
        )
        return False


def _elapsed_ms(started_at: float) -> float:
    return (perf_counter() - started_at) * 1000


def _round_trip_object(value: Any) -> dict[str, Any]:
    """插件返回的请求体必须是能经 JSON 往返的对象；返回往返后的副本。"""
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object, got {type(value).__name__}")
    try:
        serialized = json.dumps(value, ensure_ascii=False, allow_nan=False)
        return json.loads(serialized.encode("utf-8"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError(f"not JSON serializable: {exc}") from exc


def _optional_attr(hook: Any, name: str) -> Any:
    """读取钩子的可选属性；属性读取本身出错时当作没有。"""
    try:
        return getattr(hook, name, None)
    except Exception:
        return None


async def run_request_rewrite(run: PluginRun, body: dict[str, Any]) -> dict[str, Any]:
    """依次运行 request_rewrite 钩子，覆盖全部公开推理协议。

    插件抛 `PluginRejection` 时原样向外抛出（已按契约重建），链路停止。
    调用方之后需重新读取 model/stream 并替换 `run.request`。
    """
    entries = run.hooks.request_rewrite
    if not entries:
        return body
    current = body
    for entry in entries:
        current = await _rewrite_with(run, entry, current)
    return current


async def _rewrite_with(
    run: PluginRun, entry: PluginHook[RequestRewriteHook], body: dict[str, Any]
) -> dict[str, Any]:
    ctx = run.context_for(entry.plugin_id)
    draft = deepcopy(body)
    called = await _call_hook(
        _REWRITE_TIMEOUT_SECONDS, lambda: entry.hook.rewrite(draft, ctx)
    )
    stats = run.hooks.stats
    if isinstance(called.error, PluginRejection):
        stats.record(
            entry.plugin_id,
            EXT_REQUEST_REWRITE,
            outcome="rejected",
            elapsed_ms=called.elapsed_ms,
        )
        raise _coerce_rejection(called.error) from called.error
    rewritten = body
    if called.outcome == "ok" and called.value is not None:
        try:
            rewritten = _round_trip_object(called.value)
        except ValueError as exc:
            called = replace(called, outcome="invalid", error=exc)
    _record_call(stats, entry.plugin_id, EXT_REQUEST_REWRITE, called)
    return rewritten


def _coerce_rejection(exc: PluginRejection) -> PluginRejection:
    """按契约重建拒绝：插件构造后改过的状态码或消息在这里重新校验。"""
    return PluginRejection(
        getattr(exc, "status_code", 403),
        str(getattr(exc, "public_message", "") or "Rejected by a plugin"),
    )


async def apply_upstream_hooks(run: PluginRun, call: UpstreamCall) -> UpstreamCall:
    """先运行全部凭据钩子，再运行请求钩子，所以请求钩子的请求头优先。

    每个钩子只操作自己的副本，失败或返回 None 时保留之前的有效请求。
    """
    call = await _apply_upstream_stage(run, call, EXT_UPSTREAM_CREDENTIAL)
    return await _apply_upstream_stage(run, call, EXT_UPSTREAM_REQUEST)


async def apply_credential_hooks(run: PluginRun, call: UpstreamCall) -> UpstreamCall:
    """只运行凭据钩子；用于网关自己发起的请求（模型发现、探测）。"""
    try:
        return await _apply_upstream_stage(run, call, EXT_UPSTREAM_CREDENTIAL)
    finally:
        run.close()


async def _apply_upstream_stage(
    run: PluginRun, call: UpstreamCall, extension: str
) -> UpstreamCall:
    if extension == EXT_UPSTREAM_CREDENTIAL:
        entries, seconds = run.hooks.upstream_credential, _CREDENTIAL_TIMEOUT_SECONDS
    else:
        entries, seconds = run.hooks.upstream_request, _UPSTREAM_REQUEST_TIMEOUT_SECONDS
    current = call
    for entry in entries:
        if not _matches(
            run.hooks.stats, entry.plugin_id, extension, entry.hook, deepcopy(current)
        ):
            continue
        current = await _apply_upstream_with(run, entry, extension, seconds, current)
    return current


async def _apply_upstream_with(
    run: PluginRun,
    entry: PluginHook[UpstreamHook],
    extension: str,
    seconds: float,
    call: UpstreamCall,
) -> UpstreamCall:
    ctx = run.context_for(entry.plugin_id)
    draft = deepcopy(call)
    called = await _call_hook(seconds, lambda: entry.hook.apply(draft, ctx))
    applied = call
    if called.outcome == "ok" and called.value is not None:
        try:
            applied = _validate_upstream_call(called.value, call)
        except ValueError as exc:
            called = replace(called, outcome="invalid", error=exc)
    _record_call(run.hooks.stats, entry.plugin_id, extension, called)
    return applied


def _validate_upstream_call(value: Any, original: UpstreamCall) -> UpstreamCall:
    if not isinstance(value, UpstreamCall):
        raise ValueError(f"expected UpstreamCall, got {type(value).__name__}")
    if not isinstance(value.url, str):
        raise ValueError("UpstreamCall needs a str url")
    try:
        url = httpx.URL(value.url)
    except httpx.InvalidURL as exc:
        raise ValueError("invalid upstream URL") from exc
    if url.scheme not in {"http", "https"} or not url.host:
        raise ValueError("upstream URL must be absolute HTTP(S)")
    return replace(
        original,
        url=str(url),
        headers=_validate_headers(value.headers),
        body=_round_trip_object(value.body),
    )


def _validate_headers(headers: Any) -> dict[str, str]:
    """头名必须是 HTTP token，值只能是不含换行的 ASCII；否则 httpx 与响应编码会直接抛错。"""
    if not isinstance(headers, Mapping):
        raise ValueError("headers must be a mapping")
    validated: dict[str, str] = {}
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("header names and values must be str")
        if not _HEADER_NAME_PATTERN.fullmatch(key):
            raise ValueError("header names must be HTTP tokens")
        if not value.isascii() or any(
            (ord(char) < 32 and char != "\t") or ord(char) == 127 for char in value
        ):
            raise ValueError("header values must be ASCII without line breaks")
        validated[key] = value
    return validated


async def apply_response_hooks(
    run: PluginRun, response: UpstreamResponse
) -> UpstreamResponse:
    """依次运行 upstream_response 钩子；内容与响应头可改，状态码只读。"""
    current = response
    for entry in run.hooks.upstream_response:
        if not _matches(
            run.hooks.stats,
            entry.plugin_id,
            EXT_UPSTREAM_RESPONSE,
            entry.hook,
            deepcopy(current),
        ):
            continue
        current = await _apply_response_with(run, entry, current)
    return current


async def _apply_response_with(
    run: PluginRun,
    entry: PluginHook[ResponseHook],
    response: UpstreamResponse,
) -> UpstreamResponse:
    ctx = run.context_for(entry.plugin_id)
    draft = deepcopy(response)
    called = await _call_hook(
        _RESPONSE_TIMEOUT_SECONDS, lambda: entry.hook.apply(draft, ctx)
    )
    applied = response
    if called.outcome == "ok" and called.value is not None:
        try:
            applied = _validate_response(called.value, response)
        except ValueError as exc:
            called = replace(called, outcome="invalid", error=exc)
    _record_call(run.hooks.stats, entry.plugin_id, EXT_UPSTREAM_RESPONSE, called)
    return applied


def _validate_response(value: Any, original: UpstreamResponse) -> UpstreamResponse:
    """只采纳内容与响应头；渠道、协议与状态码保持原值。"""
    if not isinstance(value, UpstreamResponse):
        raise ValueError(f"expected UpstreamResponse, got {type(value).__name__}")
    if not isinstance(value.content, bytes | bytearray):
        raise ValueError("content must be bytes")
    return replace(
        original,
        headers=_validate_headers(value.headers),
        content=bytes(value.content),
    )


def rewrite_event_stream(
    run: PluginRun, chunks: AsyncIterator[bytes], *, event_format: str = "sse"
) -> AsyncIterator[bytes]:
    """改写 SSE 与 NDJSON 回复中的 JSON 对象事件。

    没有 response_event 钩子时原样返回输入迭代器。
    """
    if not run.hooks.response_event:
        return chunks
    return _rewrite_stream(run, chunks, event_format=event_format)


async def _rewrite_stream(
    run: PluginRun, chunks: AsyncIterator[bytes], *, event_format: str
) -> AsyncIterator[bytes]:
    splitter = NdjsonEventSplitter() if event_format == "ndjson" else SseEventSplitter()
    filters = [
        (entry, _resolve_event_names(entry.hook)) for entry in run.hooks.response_event
    ]
    async for chunk in chunks:
        output = bytearray()
        for piece in splitter.feed(chunk):
            if isinstance(piece, SseJsonEvent):
                output += await _rewrite_event(run, filters, piece)
            else:
                output += piece
        if output:
            yield bytes(output)
    rest = splitter.flush()
    if rest:
        if isinstance(rest, SseJsonEvent):
            yield await _rewrite_event(run, filters, rest)
        else:
            yield rest


async def _rewrite_event(
    run: PluginRun,
    filters: Sequence[tuple[PluginHook[ResponseEventHook], frozenset[str] | None]],
    event: SseJsonEvent,
) -> bytes:
    data = event.data
    for entry, names in filters:
        if names is not None and event.name not in names:
            continue
        rewritten = await _rewrite_event_with(run, entry, event.name, data)
        if rewritten is DROP_EVENT:
            return b""
        if rewritten is not None:
            data = rewritten
    return event.raw if data is event.data else event.serialize(data)


async def _rewrite_event_with(
    run: PluginRun,
    entry: PluginHook[ResponseEventHook],
    name: str,
    data: dict[str, Any],
) -> Any:
    """返回替换后的 data、`DROP_EVENT`，或 None（不改）。"""
    ctx = run.context_for(entry.plugin_id)
    try:
        event = ResponseEvent(name=name, data=deepcopy(data))
    except RecursionError:
        # 嵌套过深的事件不交给插件，原样转发。
        return None
    called = await _call_hook(
        _EVENT_TIMEOUT_SECONDS, lambda: entry.hook.rewrite(event, ctx)
    )
    rewritten: Any = None
    if called.outcome == "ok" and called.value is DROP_EVENT:
        rewritten = DROP_EVENT
    elif called.outcome == "ok" and called.value is not None:
        try:
            rewritten = _round_trip_object(called.value)
        except ValueError as exc:
            called = replace(called, outcome="invalid", error=exc)
    _record_call(run.hooks.stats, entry.plugin_id, EXT_RESPONSE_EVENT, called)
    return rewritten


def _resolve_event_names(hook: Any) -> frozenset[str] | None:
    """`events` 缺省表示全部事件；元组只接收列出的名字，空元组表示不接收。"""
    names = _optional_attr(hook, "events")
    if names is None:
        return None
    if isinstance(names, str):
        return frozenset({names})
    try:
        return frozenset(name for name in names if isinstance(name, str))
    except Exception:
        return frozenset()


async def finish_run(run: PluginRun, record: RequestRecord) -> None:
    """终态日志写入后调用一次：把请求摘要交给观察者，不阻塞客户端。重复调用不做任何事。"""
    if run._is_finished:
        return
    run._is_finished = True
    hooks = run.hooks
    if hooks.record_sink is not None and hooks.request_observer:
        observer_ids = {entry.plugin_id for entry in hooks.request_observer}
        hooks.record_sink.submit(
            record,
            hooks.request_observer,
            tuple(hooks.lifetimes[plugin_id] for plugin_id in observer_ids),
        )


def order_route_seats(
    hooks: PluginHookSet, strategy_id: str, pool: str, seats: Sequence[RouteSeat]
) -> list[int] | None:
    """按插件策略排列同优先级的候选；返回 None 表示按列出的顺序。

    同步调用并实测耗时：超过 20 ms、抛异常或不是下标的排列都按列出顺序。
    """
    entry = hooks.route_strategies.get(strategy_id)
    if entry is None or len(seats) < 2:
        return None
    started_at = perf_counter()
    try:
        order = list(entry.hook.order(pool, tuple(seats)))
    except Exception as exc:
        hooks.stats.record(
            entry.plugin_id,
            EXT_ROUTE_STRATEGY,
            outcome="error",
            elapsed_ms=_elapsed_ms(started_at),
            error=exc,
        )
        return None
    elapsed_ms = _elapsed_ms(started_at)
    try:
        indexes = [operator.index(index) for index in order]
    except Exception:
        indexes = []
    outcome = "ok"
    if sorted(indexes) != list(range(len(seats))):
        outcome = "invalid"
    if elapsed_ms > _STRATEGY_LIMIT_MS:
        outcome = "timeout"
    hooks.stats.record(
        entry.plugin_id, EXT_ROUTE_STRATEGY, outcome=outcome, elapsed_ms=elapsed_ms
    )
    return indexes if outcome == "ok" else None
