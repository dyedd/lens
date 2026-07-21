# Lens 超时设计与审查

## 结论

`request_timeout_seconds` 可以删除。它限制的是整个请求的绝对墙钟时长，而不是“请求是否失去进展”。在流式场景中，只要上游持续产生有效数据，一个长期运行的请求就是健康的；总请求 deadline 会错误终止这类请求。

当前保留两个有明确故障语义的边界：

| 配置 | 保护的阶段 | `0` 的含义 |
| --- | --- | --- |
| `first_token_timeout_seconds` | 从请求开始到首个可交付结果。流式请求等待首个有效协议输出，非流式请求等待完整响应读取完成；路由、准备和回退共享这段预算 | 禁用首字边界 |
| `stream_idle_timeout_seconds` | 首个有效流输出之后，相邻上游数据块之间的滚动等待 | 禁用流空闲边界 |

因此，正常持续输出的流没有总时长上限；停止产生数据时，首字或流空闲边界会终止它。

## 第一性原理

请求的活性可以拆成两个阶段：

```text
请求开始
   |
   | first_token_timeout_seconds
   v
首个有效协议输出
   |
   | stream_idle_timeout_seconds（每个上游数据块重新开始等待）
   v
流式请求持续输出
```

总请求超时只增加第三种规则：“无论是否持续输出，到某个墙钟时间都终止”。它既不能替代首字等待，也不能替代流空闲等待，还会破坏长上下文、长工具调用和长输出。只有产品明确要求“任何请求都不得超过固定墙钟时长”时，才应该重新引入第三种独立策略。

## 最终运行时语义

1. 请求开始时记录单调时钟，并创建共享的首字预算。
2. 路由、请求转换、每次上游尝试和回退在同一首字预算下运行。预算耗尽后不再启动下一次尝试。
3. 流式请求在等待响应头以及首个有效输出前的每次上游数据读取中使用首字预算。
4. 首字之后，每次等待下一个上游数据块使用流空闲预算；心跳或无法交付的协议片段不会错误地重置首字阶段。
5. 非流式请求的完整上游正文读取使用首字预算；内部成本统计不再被错误地计入这段上游读取超时。
6. 超时为 Lens 自己的计时器触发时，转换为 `504 gateway_timeout`。上游主动抛出的普通 `TimeoutError` 保持原样，不伪装成网关超时。
7. 流式响应的上游响应只由 `_FinalizingStreamingResponse` 关闭；客户端断开只记录为内部状态，不产生 `499`。

## 两轮审查

### 第一轮：不使用 skill 的第一性原理与对抗性审查

第一轮重点检查超时边界是否重叠、fallback 是否共享预算、主动异常是否被误分类、流式资源是否有多个所有者，以及服务重启时的请求日志是否会制造虚假延迟。

发现并修复：

| 问题 | 修复方法 |
| --- | --- |
| 总请求 timeout 与首字、流空闲 timeout 语义重叠，并会截断持续健康的长流 | 删除 `request_timeout_seconds` 的存储、运行时、UI、README 和生命周期依赖 |
| `asyncio.timeout()` 产生的普通 `TimeoutError` 与业务代码主动抛出的 `TimeoutError` 无法区分 | 增加 `_GatewayTimeoutError`，并通过 `asyncio.timeout().expired()` 只转换真正由 Lens 计时器触发的异常 |
| 流式响应、内层迭代器和取消处理分别清理上游响应，所有权不清晰 | 将响应关闭、迭代器关闭和后台任务顺序收敛到 `_FinalizingStreamingResponse` |
| 流式 4xx/5xx 为读取错误正文而继续等待，可能把明确的上游状态覆盖成 504 | 响应头已到达时立即保留原 HTTP 状态；只有已消费的非流式响应才读取可用正文详情 |
| 重启时用已删除的总 timeout 裁剪停机日志延迟，并把停机时间当成请求耗时 | `fail_running_request_logs()` 只标记中断状态和错误，不再合成停机期间的延迟 |
| 合法的 `0ms` 首字延迟被 `value or elapsed` 重新计算 | 保留已计算的零值，不使用真假值兜底 |

### 第二轮：使用 `code-review-skill`

第二轮按错误处理、异步资源所有权、取消传播、React/TypeScript 表单和过度优化清单重新检查最新 `HEAD` 差异。

发现并修复：

| 问题 | 修复方法 |
| --- | --- |
| 流式请求遇到非 SSE JSON 响应时，首字 timeout scope 包住了成本统计；模型价格存储慢会被误报为上游首字超时 | 只在首字 scope 内读取上游正文，解析、转换和成本统计放在 scope 外 |
| 流式发送异常时，`finally` 中失败的后台请求日志可能覆盖原始流异常 | `_FinalizingStreamingResponse` 在已有异常时记录清理失败并重新抛出原始异常；正常流结束时仍保留后台任务的正常错误传播语义 |
| `_mark_stream_disconnected()` 只有一个调用点，且不包含独立行为 | 删除单调用点 helper，在唯一的资源所有权边界直接写入断开状态 |
| 删除总请求配置后仍保留 `REQUEST_TIMEOUT_SECONDS_MAX` 名称，造成旧语义残留 | 改名为 `GATEWAY_TIMEOUT_SECONDS_MAX` |
| `TimeoutKind` 只在内部使用，却暴露为模块级公共名称 | 收敛为 `_TimeoutKind` |

审查中确认不是冗余、因此保留的代码：

- `_GatewayTimeoutError` 是错误分类边界，不是重复包装。
- `timeout_scope.expired()` 是区分计时器取消和内部主动 `TimeoutError` 的必要判断。
- `response = None` 表示上游响应所有权已经转移给流式响应对象，避免调用方提前关闭它。
- 首字预算和流空闲预算分别对应不同的活性不变量，不能合并成一个“更通用”的 timeout。
- `body_iterator.aclose()` 与 `httpx.Response.aclose()` 关闭的是不同层级的资源，不能因为都叫 close 就删除其一。

## 错误与资源边界

```text
Lens 计时器到期
    -> _GatewayTimeoutError
    -> 504 / gateway_timeout

上游 HTTP 状态
    -> 保留上游 status_code
    -> fallback / upstream_error

上游传输错误
    -> 502 / upstream_error

客户端断开
    -> is_client_disconnected=True
    -> 不产生 499，不计入路由成功或失败
```

流式资源的关闭顺序固定为：

```text
标记客户端断开（仅未完成且没有已记录错误时）
    -> 关闭 body iterator
    -> 关闭 httpx 上游响应
    -> 运行请求日志后台任务
```

如果流本身已经抛出异常，清理阶段的次生异常只记录，不覆盖原始异常。这样不会把真正的传输或协议错误伪装成日志写入错误。

## 配置面变更

- 后端 editable settings、runtime settings 和共享 setting key 只保留 `first_token_timeout_seconds`、`stream_idle_timeout_seconds`。
- 管理界面移除总请求 timeout，增加首字和流空闲两个字段，均允许 `0`，最大值为 `86400` 秒。
- `README.md` 和 `README_EN.md` 已同步新的配置语义。
- 未创建 `TIMEOUT_REVIEW.md`；本文件覆盖其审查内容。

## 验证

已执行：

- 受影响后端 API 测试：`21 passed`
- `python -m compileall -q lens_api`
- 受影响模块 `py_compile`
- `pnpm exec tsc --noEmit`
- `pnpm lint`
- `git diff --check`
- `git diff --cached --check`
- 最小运行时复现：确认 Lens 计时器产生 `_GatewayTimeoutError`，内部 `TimeoutError` 原样传播
- 最小流响应复现：确认后台清理失败不会覆盖原始流异常
