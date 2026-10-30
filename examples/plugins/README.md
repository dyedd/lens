# 插件

Lens 的插件用来扩展网关的边界：在请求进入路由前改写或拒绝它，在发往上游时改写请求或换凭据，在回到客户端前改写回复，观察已完成的请求，为渠道补充模型，或给模型组提供路由顺序。计划任务、设置等平台能力不属于插件。

## 安装

把插件目录（或单个 `.py` 文件）放进插件目录：

```
data/plugins/<plugin_id>/plugin.py     # 目录形式，可用相对导入拆分模块
data/plugins/<plugin_id>.py            # 单文件形式
```

插件目录默认 `./data/plugins`，可用 `LENS_PLUGINS_DIR` 覆盖。Docker 部署时 `./data` 已挂载到 `/app/data`。

Lens 每 2 秒检查一次插件目录，文件有变化就自动重新加载，无需重启；设置页的「重新扫描」按钮与 `POST /api/admin/plugins/reload` 效果相同。只有文件变化的插件会重新注册，进行中的请求继续使用开始时的插件。插件自己的数据请放在插件目录以外，否则每次写入都会触发重新加载。

导入失败或没有导出 `PLUGIN` 的插件会以「异常」状态出现在 **设置 → 插件**，并显示原因。

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
        return None  # 不改


def register(context: PluginContext) -> None:
    context.add_request_rewrite_hook(WordGuard())


PLUGIN = PluginDefinition(manifest=MANIFEST, register=register)
```

`id` 用小写字母、数字与下划线。`api_version` 默认与当前内核一致，不一致的插件标记为「异常」。

## 扩展点

钩子都是 `async`（路由策略除外）。插件出错、超时或返回值不合法时，Lens 记录日志与统计并按原样继续（fail open）；`PluginRejection` 是唯一会改变请求结果的异常。返回 `None` 表示不改；就地修改而不返回的内容会被丢弃。

| 标识 | 登记方法 | 接口 | 时机 | 超时 |
| --- | --- | --- | --- | --- |
| `request_rewrite` | `add_request_rewrite_hook` | `rewrite(body, ctx) -> dict \| None` | 路由前，每个请求一次；只作用于 Chat、Responses、Anthropic、Gemini 入口 | 250 ms |
| `upstream_credential` | `add_upstream_hook` | `matches(call)` / `apply(call, ctx) -> UpstreamCall \| None` | 每次上游尝试，协议转换之后；先于 `upstream_request` | 15 s |
| `upstream_request` | `add_upstream_hook` | 同上 | 每次上游尝试，凭据钩子之后 | 250 ms |
| `upstream_response` | `add_response_hook` | `matches(response)` / `apply(response, ctx) -> UpstreamResponse \| None` | 非流式回复转换成客户端协议之后 | 250 ms |
| `response_event` | `add_response_event_hook` | `rewrite(event, ctx) -> dict \| DROP_EVENT \| None` | 流式（SSE）回复的每个事件 | 50 ms |
| `request_observer` | `add_request_observer` | `completed(record) -> None` | 请求结束后，经队列异步投递 | 250 ms |
| `model_catalog` | `add_model_catalog_hook` | `matches(channel)` / `models(channel) -> [CatalogEntry]` | 渠道模型同步 | 30 s |
| `route_strategy` | `add_route_strategy` | `name` / `order(pool, seats) -> [int]` | 模型组选择该策略时，每个优先级档 | 20 ms |

- **请求改写**：返回的新请求体可以改 `model`、`stream` 与工具声明，网关密钥的模型白名单按改写后的模型检查。抛 `PluginRejection(status, message)` 拒绝，客户端按其协议收到该状态码（400–599）与消息。请求日志保留客户端的原始请求。
- **出站请求**：`UpstreamCall` 含渠道、协议、URL、请求头、请求体、凭据 id 与目标模型 `model_name`。每次尝试都从新转换的请求体开始，上一次尝试的改动不会带到下一次。模型发现与测速这类网关自己发起的请求只运行凭据钩子。请求头名需为合法 token、值为 ASCII，否则改动被丢弃。
- **非流式回复**：可以改 `content` 与 `headers`，客户端收到改动后的结果；`status_code` 只读。用量与计费按改写前的上游回复统计。
- **流式事件**：只处理只有一行 `data:` 且是 JSON 对象的事件；`[DONE]`、注释与心跳原样转发。返回 dict 替换数据，返回 `DROP_EVENT` 丢弃事件（后面的插件看不到它）。可选的 `events` 属性只接收列出的事件名（`event:` 行；Chat 与 Gemini 流为 `""`）。
- **请求观察**：每个请求在最终状态（成功、失败或取消）时投递一次 `RequestRecord`，只含白名单字段，不含请求体、提示词或错误原文。队列容量 1024，满了丢弃并计入统计；观察者不会拖慢请求。
- **路由策略**：在路由锁内同步调用，只决定同优先级候选的顺序，返回下标的一个排列；超时、抛异常或返回值不是排列时按原顺序。不要在 `order` 里调用路由器。模型组用 `<插件 id>/<name>` 选中策略（总长不超过 32 个字符）；插件停用时该模型组按成员顺序尝试，保存的策略不变。

同一插件的各个钩子在一次请求里共享 `ctx.state`（一个字典），`ctx.request` 是请求的只读摘要：协议、路径、模型、是否流式与 User-Agent。

## 设置

清单里声明设置项，Lens 为它生成表单，值在 `context.settings` 里读取：

```python
settings=(
    PluginSetting(key="threshold", label="阈值", type="float", default=0.5, min_value=0, max_value=1),
    PluginSetting(key="api_key", label="密钥", type="string", default="", secret=True),
),
```

类型支持 `bool` / `int` / `float` / `string` / `enum`（`enum` 需给 `options`）。`min_value` / `max_value` 用于数字；`secret` 用于字符串，管理端不回显它的值，只显示是否已设置。保存设置后插件重新注册，新值立即生效。默认值违反自己的约束时插件标记为「异常」。

## 依赖、清理与计划任务

- `requires=("other_plugin",)`：依赖停用或缺失时，本插件进入「等待依赖」，不挂任何扩展点。
- `context.on_dispose(fn)`：插件停用、设置变化或重新加载时调用，按登记的逆序执行，可以是 `async`。
- `context.add_cronjob(spec, handler)`：追加计划任务；与平台任务同 id 的任务会被忽略。

钩子在事件循环里运行，阻塞的同步代码无法被超时打断，请用异步 I/O。设置页按扩展点显示调用次数、失败次数、平均耗时与最近一次错误。

## 目录里的示例

- [`request_counter`](request_counter/plugin.py)：只读观察者，记录每个完成的请求。
- [`channel_credential_bridge`](channel_credential_bridge/plugin.py)：为 `channel_ids` 里列出的渠道换用插件签发的凭据、加标记头，并补充一个模型。
- [`response_header_stamp`](response_header_stamp/plugin.py)：给非流式回复加标记头，并依赖 `channel_credential_bridge`。

复制到插件目录即可使用。
