# 插件开发

Lens 的插件用来扩展网关的边界：在请求进入路由前改写或拒绝它，在发往上游时改写请求或换凭据，在回到客户端前改写回复，观察已完成的请求，或给模型组提供路由顺序。插件也可以声明设置和追加计划任务。

开发前先确定要改变哪个阶段。一个插件可以登记多个钩子，但只需要使用实际影响行为的扩展点：

| 需求 | 使用的扩展点 | 判断依据 |
| --- | --- | --- |
| 修改客户端模型名、调整输入或拒绝请求 | `request_rewrite` | 改动必须参与后续权限检查与路由 |
| 为选中的上游获取短期令牌 | `upstream_credential` | 已确定渠道、Key 和目标模型；模型发现与测试也会使用 |
| 增加供应商专用请求头或参数 | `upstream_request` | 请求已经转换为该供应商协议；每次尝试分别执行 |
| 给普通回复加响应头或调整内容 | `upstream_response` | 已经取得非流式结果，并转换回客户端协议 |
| 调整流式 JSON 事件 | `response_event` | 需要逐事件处理；普通响应钩子不处理流式内容 |
| 记录请求完成后的统计摘要 | `request_observer` | 只观察终态，不参与客户端响应 |
| 给可用成员排序 | `route_strategy` | 复用 Lens 的候选过滤、冷却和调用流程 |

这些钩子在一次网关请求中的位置见 [系统架构](./architecture#一次请求如何完成)。

## 安装

把插件目录（或单个 `.py` 文件）放进插件目录：

```
data/plugins/<plugin_id>/plugin.py     # 目录形式，可用相对导入拆分模块
data/plugins/<plugin_id>.py            # 单文件形式
```

插件目录默认 `./data/plugins`，可用 `LENS_PLUGINS_DIR` 覆盖。Docker 部署时 `./data` 已挂载到 `/app/data`，安装的插件从 `/app/data/plugins` 加载。镜像只包含插件运行框架，已安装插件和仓库 examples/plugins 中的示例均不打包。

Lens 每 2 秒检查一次插件目录，文件有变化就自动重新加载，无需重启；设置页的「重新扫描」按钮与 `POST /api/admin/plugins/reload` 效果相同。只有文件变化的插件会重新注册，进行中的请求继续使用开始时的插件。插件自己的数据请放在插件目录以外，否则每次写入都会触发重新加载。

导入失败或没有导出 `PLUGIN` 的插件会以「异常」状态出现在 **设置 → 插件**，并显示原因。

![设置中的插件列表、启停状态与调用统计](/images/plugins.png)

插件代码在 Lens 进程中执行，拥有该进程的权限。安装前审查插件来源和它访问的数据。

## 写一个插件

模块导出 `PLUGIN = PluginDefinition(manifest=..., register=...)`。`register(context)` 在插件启用时调用，把扩展点登记到 `context` 上：

```python
from app.plugins.contract import (
    EXT_REQUEST_REWRITE,
    HookContext,
    PluginContext,
    PluginDefinition,
    PluginManifest,
    PluginRejection,
)

MANIFEST = PluginManifest(id="word_guard", name="敏感词拦截", version="0.1.0", author="you")


class WordGuard:
    def extension(self) -> str:
        return EXT_REQUEST_REWRITE

    async def rewrite(self, body: dict, ctx: HookContext) -> dict | None:
        if "forbidden" in str(body.get("messages", "")):
            raise PluginRejection(400, "Request contains a blocked word")
        return None


def register(context: PluginContext) -> None:
    context.add_request_rewrite_hook(WordGuard())


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
```

`id` 用小写字母、数字与下划线。`api_version` 默认与当前内核一致，不一致的插件标记为「异常」。

上面的代码保存为 `data/plugins/word_guard/plugin.py` 后，Lens 先导入模块并读取 `PLUGIN`，再在启用时调用 `register`。注册只负责把 `WordGuard` 实例挂到请求改写阶段；每次请求执行的是它的 `rewrite`。

在 Chat 请求中，`messages` 含有 `forbidden` 时抛出 `PluginRejection`，请求在选择上游前结束；其他输入返回 `None`，继续使用原请求体。这个示例只检查 Chat 的 `messages`，不读取 Responses 的 `input`，也不作为完整内容审核方案。需要覆盖其他协议时，依据 `ctx.request.protocol` 处理对应的输入字段。

钩子收到的是隔离的输入副本。需要改写时，应返回修改后的字典；只改副本然后返回 `None` 不会改变实际请求。若修改 `model`，网关会用新名称检查 Key 权限和生成路由计划，不能用改写绕过模型白名单。

## 扩展点

钩子都是 `async`（路由策略除外）。插件出错、超时或返回值不合法时，Lens 记录日志与统计并按原样继续（fail open）；只有请求改写钩子抛出的 `PluginRejection` 会主动拒绝请求；其他扩展点中的异常仍按 fail open 处理。返回 `None` 表示不改；就地修改而不返回的内容会被丢弃。

| 标识 | 登记方法 | 接口 | 时机 | 超时 |
| --- | --- | --- | --- | --- |
| `request_rewrite` | `add_request_rewrite_hook` | `rewrite(body, ctx) -> dict \| None` | 路由前，每个请求一次；覆盖全部推理协议与图像编辑表单字段 | 250 ms |
| `upstream_credential` | `add_upstream_hook` | `matches(call)` / `apply(call, ctx) -> UpstreamCall \| None` | 每次上游尝试，协议转换之后；先于 `upstream_request` | 15 s |
| `upstream_request` | `add_upstream_hook` | 同上 | 每次上游尝试，凭据钩子之后 | 250 ms |
| `upstream_response` | `add_response_hook` | `matches(response)` / `apply(response, ctx) -> UpstreamResponse \| None` | 非流式回复转换成客户端协议之后 | 250 ms |
| `response_event` | `add_response_event_hook` | `rewrite(event, ctx) -> dict \| DROP_EVENT \| None` | 流式（SSE、NDJSON）回复的每个 JSON 对象事件 | 50 ms |
| `request_observer` | `add_request_observer` | `completed(record) -> None` | 请求结束后，经队列异步投递 | 250 ms |
| `route_strategy` | `add_route_strategy` | `name` / `order(pool, seats) -> [int]` | 模型组选择该策略时，每个优先级档 | 20 ms |

- **请求改写**：覆盖 Chat、Responses、Anthropic、Gemini、Embedding、图像和 Rerank。返回的新请求体可以改 `model`、`stream` 与协议字段，网关密钥的模型白名单按改写后的模型检查；Embedding 与 Rerank 始终为非流式。图像编辑的 `body` 是表单字段，上传文件由网关保留。抛 `PluginRejection(status, message)` 拒绝，客户端按其协议收到该状态码（400–599）与消息。请求日志保留客户端的原始请求。
- **出站请求**：`UpstreamCall` 含渠道、协议、URL、请求头、请求体、凭据 id 与目标模型 `model_name`。只采纳合法 HTTP(S) URL、请求头和可编码为 JSON 的请求体；渠道、协议、凭据 id 与目标模型是只读事实。每个钩子在副本上运行，失败或返回 `None` 时保留此前的请求。每次上游尝试都从新转换的请求体开始。模型发现与测速只运行凭据钩子，持久化模型组成员的测速保留真实渠道 id。请求头名需为合法 token、值为 ASCII，否则改动被丢弃。
- **非流式回复**：可以改 `content` 与 `headers`，客户端收到改动后的结果；`status_code` 只读。用量与计费按改写前的上游回复统计。
- **流式事件**：覆盖所有协议的 SSE JSON 对象事件和 NDJSON 对象行；SSE 只改写只有一行 `data:` 的事件。`[DONE]`、注释与心跳原样转发。返回 dict 替换数据，返回 `DROP_EVENT` 丢弃事件（后面的插件看不到它）。可选的 `events` 属性只接收列出的事件名（`event:` 行；未命名事件与 NDJSON 行为 `""`）。用量与计费按改写前的回复统计。
- **请求观察**：每个请求在最终状态（成功、失败或取消）时投递一次 `RequestRecord`，只含白名单字段，不含请求体、提示词或错误原文。队列容量 1024，满了丢弃并计入统计；观察者不会拖慢请求。
- **路由策略**：在路由锁内同步调用，只决定同优先级候选的顺序，返回下标的一个排列；超时、抛异常或返回值不是排列时按原顺序。不要在 `order` 里调用路由器。模型组用 `<插件 id>/<name>` 选中策略（总长不超过 32 个字符）；插件停用时该模型组按成员顺序尝试，保存的策略不变。

### 在哪里保存插件状态

`ctx.request` 是请求的只读摘要：协议、路径、模型、是否流式与 User-Agent。需要在多个钩子之间传递本次请求的数据时，使用 `ctx.state`：

| 数据 | 保存位置 | 生命周期 |
| --- | --- | --- |
| 这次请求的标记、阶段间中间结果 | `ctx.state` | 同一插件、同一次请求的钩子共享 |
| 这次上游尝试的 URL、头部、请求体 | `UpstreamCall` 的输入和返回值 | 每次重试重新构造 |
| 插件设置 | `context.settings`，在注册时读取 | 当前注册使用的设置快照 |
| HTTP 客户端、缓存等跨请求资源 | `register` 创建的对象或钩子实例 | 当前注册存活期间，由 `on_dispose` 清理 |

假设一次请求先调用 A，再调用 B，出站钩子会运行两次，但同一插件仍使用这次请求的 `ctx.state`。下一次客户端请求会得到新的状态字典。钩子实例可被并发请求调用，因此不要把“当前用户”“当前请求体”这类请求数据写到实例字段或模块全局变量中。

### 异常会怎样影响请求

`PluginRejection` 仅在请求改写阶段用于明确拒绝。普通异常、超时或不合法返回值会使本次改写失效，网关沿用此前结果继续处理，并记录插件错误。例如出站钩子返回了不合法 URL，不会把该 URL 发往上游。

这是插件的故障放行行为。若插件承担内容拦截，应明确区分“识别到禁止内容后主动拒绝”和“插件自身执行出错后放行”，并监控失败统计。请求观察者使用有界队列，队列满会丢弃摘要，因此不适合要求逐条必达的账务记录。

## 设置

先从 `app.plugins.contract` 导入 `PluginSetting`，再把下面的 `settings` 参数放进 `PluginManifest(...)`。Lens 为它生成表单，注册时从 `context.settings` 读取值：

```python
settings=(
    PluginSetting(key="threshold", label="阈值", type="float", default=0.5, min_value=0, max_value=1),
    PluginSetting(key="api_key", label="密钥", type="string", default="", secret=True),
),
```

类型支持 `bool` / `int` / `float` / `string` / `enum`（`enum` 需给 `options`）。`min_value` / `max_value` 用于数字；`secret` 用于字符串，管理端不回显它的值，只显示是否已设置。保存设置后插件重新注册，新值立即生效。默认值违反自己的约束时插件标记为「异常」。

例如在 `register(context)` 中读取 `context.settings["threshold"]`，并传给钩子实例。设置由 Lens 按声明类型校验后交给注册函数，插件无需重复猜测类型；但仍需校验设置代表的业务含义，例如远程服务是否接受这个参数。

设置与启停状态保存在数据库。通过设置 API 传入 `null` 会恢复该项默认值，密钥项传空字符串表示保留原值。`secret=True` 只控制管理端隐藏显示，不能据此认为数据库中的值已加密。

## 启停与热加载的生命周期

一次请求开始时取得插件扩展点快照，后续改写、上游尝试、响应事件和终态观察都沿用它。这样一条长流式响应不会在中途混用两个插件版本。

下面的“立即生效”指当前 Lens 进程。多个 worker 共用数据库时，插件设置不会自动广播到其他进程，详见 [状态由谁保存](./architecture#状态由谁保存)。

| 操作 | 后续请求 | 已经开始的请求 |
| --- | --- | --- |
| 启用插件 | 注册成功后使用新钩子 | 沿用原快照 |
| 停用插件 | 不再使用该插件 | 继续使用原钩子直到结束 |
| 修改设置 | 重新注册后使用新设置 | 继续使用旧设置与资源 |
| 修改源文件并重新加载 | 加载成功后使用新版本 | 继续使用旧版本 |
| 依赖缺失或停用 | 插件进入“等待依赖”，不登记扩展点 | 旧注册等待其使用者结束后清理 |

旧注册退出后，Lens 等待使用它的请求、流式响应、观察回调和计划任务释放引用，再执行 `context.on_dispose(...)` 登记的清理函数。因此停用按钮返回成功，并不表示旧 HTTP 客户端已经立即关闭。

资源应在注册时创建，并马上登记清理。例如使用 `httpx.AsyncClient` 时，将它的 `aclose` 方法交给 `context.on_dispose`，不要每次调用钩子都创建新连接池，也不要在停用时手工关闭仍被请求使用的对象。`register` 本身是同步函数；远程 I/O 放到异步钩子或计划任务中执行。

## 依赖与计划任务

- `requires=("other_plugin",)`：依赖停用或缺失时，本插件进入「等待依赖」，不挂任何扩展点。
- `context.on_dispose(fn)`：插件停用、设置变化或重新加载后，等待旧请求、观察回调与计划任务结束再调用，按登记的逆序执行，可以是 `async`。
- `context.add_cronjob(spec, handler)`：追加计划任务；与平台任务同 id 的任务会被忽略。

钩子在事件循环里运行，阻塞的同步代码无法被超时打断，请用异步 I/O。设置页按扩展点显示调用次数、失败次数、平均耗时与最近一次错误。

## 可运行示例

- [`request_counter`](https://github.com/dyedd/lens/blob/main/examples/plugins/request_counter/plugin.py)：只读观察者，记录每个完成的请求。
- [`channel_credential_bridge`](https://github.com/dyedd/lens/blob/main/examples/plugins/channel_credential_bridge/plugin.py)：为 `channel_ids` 里列出的渠道换用插件签发的凭据、加标记头。
- [`response_header_stamp`](https://github.com/dyedd/lens/blob/main/examples/plugins/response_header_stamp/plugin.py)：给非流式回复加标记头，并依赖 `channel_credential_bridge`。

复制到插件目录即可使用。

## 验证插件

1. 按 [开发环境](./setup) 启动 Lens，并使用单独的测试数据库和插件目录。
2. 将上面的代码保存为 `data/plugins/word_guard/plugin.py`。在 **设置 → 插件** 点击重新扫描，确认插件已启用，且没有加载错误。
3. 准备可用模型组和网关 Key，按 [客户端接入](../guide/clients) 的 Chat 示例发送普通请求，应得到正常回复。
4. 将用户消息改为 `forbidden`，应收到 HTTP 400 和 `Request contains a blocked word`。请求日志应记录失败，且没有上游尝试。
5. 停用插件，再发送相同消息，应恢复正常上游调用。重新启用后，再检查拦截与调用统计。

修改代码后重复正常路径和插件路径。不要只验证模块能导入；需要确认注册、实际钩子调用、启停和热加载的行为。

还应按插件实际使用的能力补充以下检查：

| 使用的能力 | 验证方法 |
| --- | --- |
| 修改设置 | 保存新值后发新请求，确认行为变化；长请求仍按开始时的设置完成 |
| 出站钩子 | 用隔离的演示上游记录收到的 URL、头部与请求体，确认每次重试都执行 |
| 响应或流式钩子 | 分别发送普通请求与 `stream: true` 请求；检查结果、结束事件和取消后的清理 |
| 热加载与资源清理 | 请求进行中修改插件，再发新请求；确认旧请求可结束，新请求使用新版本 |
| 异常处理 | 主动制造一次异常，确认插件统计记录失败，且网关按既定放行行为继续 |

找不到插件时先查目录与 `PLUGIN` 导出；显示“异常”时查导入、版本和设置声明；显示“等待依赖”时查 `requires`；显示“已启用”但不改请求时查扩展点、`matches` 条件和返回值。

扩展点类型以 [contract.py](https://github.com/dyedd/lens/blob/main/backend/app/plugins/contract.py) 为准，超时与返回值处理见 [runtime.py](https://github.com/dyedd/lens/blob/main/backend/app/plugins/runtime.py)。
