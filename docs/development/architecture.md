# 系统架构

Lens 把“客户端要哪个模型”和“实际调用哪个供应商”分开。客户端使用模型组名称和网关 Key；Lens 从已保存的组成员中选择地址、上游 Key 和模型，转换请求与回复，并记录每次尝试。

本页面向需要理解或修改 Lens 的开发者。下面沿用一个纯文本请求示例：客户端通过 Responses 接口请求 `daily-chat`；这个别名指向执行组 `gpt-6.1-sol`，组内依次配置主供应商 A、备用供应商 B，二者都提供 OpenAI Chat 接口。假设 A 返回 429、B 返回 200，观察 Lens 如何完成这一次请求。

示例用于说明协议转换与故障切换。[GPT-6.1 Sol 的工具调用需要 Responses API](https://developers.openai.com/api/docs/models/gpt-6.1-sol)；使用工具时，应为该模型配置 Responses 上游出口。

## 系统由哪些部分组成

管理界面和推理客户端访问同一个 FastAPI 应用，但使用不同的接口和认证。管理界面负责配置与查询；推理客户端只提交模型请求。Docker 部署会把管理界面编译为静态文件，由后端一并提供。

[![管理界面通过管理服务保存配置，推理客户端通过请求编排访问路由器与上游，二者使用同一个数据库](/images/architecture.svg)](/images/architecture.svg)

*模块关系示意。框中的请求编排、路由器和持久化层是同一 Lens 进程内的模块。图中省略插件与计划任务，后文分别说明。本页机制图均可点击查看原图。*

| 组成部分 | 输入与输出 | 负责的决定 |
| --- | --- | --- |
| 管理界面与管理 API | 表单 / 查询条件 → 配置、日志与统计 | 用户要保存或查看什么；管理 API 校验并调用仓储 |
| 推理入口 | HTTP 路径、网关 Key、请求体 → 已识别协议的请求 | 认证、读取 JSON 或上传表单，识别客户端协议 |
| 请求编排 | 请求、运行设置、组成员 → 最终响应 | 在什么阶段调用路由、转换、上游、插件和日志 |
| 路由器 | 候选、分发策略、健康与冷却状态 → 本次调用目标 | 选谁先调用；失败后选谁；是否允许恢复探测 |
| 协议转换与上游传输 | 一次调用目标与请求 → 上游结果 | 构造 URL、鉴权、协议字段；发送并读取响应 |
| 持久化层 | 领域对象与查询条件 → 数据库记录 | 配置和日志如何写入、查询与恢复 |

源码入口：[create_app](https://github.com/dyedd/lens/blob/main/backend/app/api/app.py)、[接口装配](https://github.com/dyedd/lens/blob/main/backend/app/api/route_table.py)、[AppState](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/app_state.py)。

## 从界面配置到一个调用目标

### 站点、出口和成员的区别

界面中的一条“渠道”记录对应一个站点 `Site`。站点保存供应商地址、Key、模型和规则；路由时会把它展开成更具体的协议出口。

| 对象 | 本例中的值 | 保存或生成的内容 |
| --- | --- | --- |
| 站点 `Site` | 主供应商 A | 名称、启停、地址、凭证、代理及请求规则 |
| 地址 `SiteBaseUrl` | A 的 Base URL | URL 和用途，例如默认、Chat 或模型列表 |
| 凭证 `Credential` | A-Key | 上游密钥、适用地址、模型同步规则和倍率配置 |
| 协议配置 `SiteProtocolConfig` | A 地址的调用配置 | 绑定的地址、Key 与模型；每个模型记录其上游协议 |
| 运行时渠道 `ChannelConfig` | A 的 Chat 出口 | 从协议配置展开，ID 为 `{protocol_config_id}_{protocol}` |
| 组成员 | A 的 Chat 出口 + A-Key + `gpt-6.1-sol` | 模型组内已保存的成员、顺序、启停和来源 |
| 路由目标 `RouteTarget` | 本次向 A 发出的调用 | 具体出口、凭证、上游模型、有效上下文窗口 |

`flatten_site` 按协议展开配置。标为“模型列表”的地址只用于发现模型，不成为推理候选；Key 的适用地址决定它能在哪些出口使用。对应实现见 [channel_store/mapping.py](https://github.com/dyedd/lens/blob/main/backend/app/persistence/channel_store/mapping.py)。

**不同 Key 是不同成员；同一个 Key 的多个地址或协议是调用出口。** 数据库成员用“运行时渠道 + 凭证 + 上游模型”定位；轮询选择时，再按“站点 + 凭证 + 上游模型”合并同一成员的多个出口，避免多填一个地址就多占一个轮询位置。其余出口仍可用于故障切换，见 [RoutePlanner](https://github.com/dyedd/lens/blob/main/backend/app/gateway/router/routing.py)。

### 模型目录怎样进入模型组

模型先保存在站点中，再成为可供请求使用的组成员：

1. **发现与同步模型**：按地址和 Key 拉取上游目录，使用该 Key 的模型规则筛选，再保存具体模型、协议和上下文。没有同步规则的 Key 跳过自动同步；拉取失败时保留该目标已有模型。
2. **重新归组**：按照组名与正则规则加入匹配模型，处理未分配模型，并移除失效或不再匹配的自动成员。手动成员不会仅因匹配规则改变而被移除。
3. **保存归组结果**：成员写入数据库。后续请求读取这些成员，不在每次推理时临时扫描上游目录或重新做名称匹配。

渠道保存、模型组保存、模型同步和应用启动都会触发相关归组过程。“同步规则”决定站点保留哪些上游模型，“模型组规则”决定这些模型加入哪些组，二者不是同一条规则。精确示例见 [渠道同步规则](../guide/sites#控制自动同步范围) 和 [模型组匹配规则](../guide/model-groups#设置匹配范围)。

实现位置：[model_sync.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/tasks/model_sync.py)、[group_reconcile.py](https://github.com/dyedd/lens/blob/main/backend/app/persistence/repositories/group_reconcile.py)。

### 别名怎样找到两个候选

本例先把 `gpt-6.1-sol` 执行组限制为精确匹配，再建立 `daily-chat` 别名。模型组编辑器中的“直接调度”对应执行组，“别名”对应引用执行组的路由组。

[![daily-chat 别名引用 gpt-6.1-sol 执行组，执行组按顺序保存 A-Key 和 B-Key 的两个上游成员](/images/routing-example.svg)](/images/routing-example.svg)

*配置关系示意。客户端填写 `daily-chat`；上游请求使用成员记录中的 `gpt-6.1-sol`。箭头表示引用与成员关系，不表示同时发送两次请求。*

`resolve_routing_plan` 先查到 `daily-chat`，再加载它引用的执行组。别名必须直接引用执行组，不能再串到另一个别名。计划里同时保留请求组名和执行组名，便于日志区分“客户端调用了谁”和“谁实际提供成员”。

随后，路由器会：

- 过滤禁用、失效或无法到达客户端协议的成员。
- 优先采用成员的上下文窗口，缺失时用执行组默认值。估算请求过长时过滤已知不足的候选；若一个候选都无法确认适合，则保留原池，由上游判断。
- 在同一地址配置、Key 和模型的出口中，优先保留原生协议；再结合地址用途、冷却和组策略选择顺序。
- 对故障切换组按配置顺序尝试；对平滑轮询组按健康权重选成员。故障后成功的成员还可能在短期内被复用。

这些步骤产生候选计划，并不在此时调用上游。具体边界见 [routing_plan.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/proxy/routing_plan.py) 和 [router/routing.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/router/routing.py)。

## 一次请求如何完成

客户端发送的核心内容如下，认证头中放的是 Lens 网关 Key：

```http
POST /v1/responses
Authorization: Bearer <Lens 网关 Key>
Content-Type: application/json

{"model":"daily-chat","input":"hello"}
```

假设两名候选最初均可用、A 先返回 429、B 随后成功。下图省略配置读取和数据库写入，重点显示请求顺序：

[![客户端的一次 Responses 请求先调用 A，A 返回 429 后调用 B，B 成功后 Lens 转为 Responses 格式返回](/images/request-failover.svg)](/images/request-failover.svg)

*非流式请求时序示意。一次客户端请求可以产生多次上游尝试；A 的错误先进入尝试记录，B 成功后客户端收到最终成功响应。*

### 入口认证与请求准备

`/v1/responses` 进入 `proxy_openai_responses`，依赖 `get_current_gateway_key` 检查 Key 是否存在、启用、到期或达到费用上限。管理端 JWT 和供应商 Key 不用于这一步。

入口把请求交给 `proxy_protocol`。编排层读取渠道与运行设置，创建本次请求的共享超时预算，以及一份插件扩展点快照。读取出有效模型名后创建“连接中”日志，再运行请求改写插件。如果插件改了 `model`，模型权限检查和后续路由使用改写后的模型名；请求正文日志保留客户端原始内容。

认证失败发生在推理编排之前，通常不会产生这里的请求日志行。因此，排查“客户端收到 401、日志里却没有请求”时，应先检查网关 Key，而不是直接检查上游。实现见 [proxy_routes.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/proxy_routes.py)、[auth.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/auth.py) 和 [proxy_flow.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/proxy/proxy_flow.py)。

### 为选中的成员生成上游请求

路由计划把 `daily-chat` 解析为 `gpt-6.1-sol` 执行组，并先选中 A。客户端协议是 Responses，A 的上游协议是 Chat，因此本次请求需要转换：

```text
客户端请求                  统一请求结构                 A 的上游请求
Responses input: "hello" → 文本消息、工具等公共字段 → Chat messages: [...]
model: daily-chat                                      model: gpt-6.1-sol
```

转换后依次应用全局、渠道、请求模型组的参数规则，后面的规则可以覆盖前面的字段；模型名由选中的成员决定。再生成上游 URL 和鉴权头，执行凭据钩子、出站请求钩子，最后通过共享 HTTP 客户端发送。

换到 B 时，会从本次请求的输入重新生成 B 的请求，不会把 A 已经转换或改写过的请求体再改一遍。这样 A、B 使用不同协议或参数规则时，也能各自构造请求。实现见 [proxy_attempt.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/proxy/proxy_attempt.py)、[upstream_request.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/upstream_request.py) 和 [参数规则顺序](https://github.com/dyedd/lens/blob/main/backend/app/core/upstream_rules.py)。

### A 失败后怎样处理

A 的 429 被记录为一次失败尝试。默认策略将它归为 Key 限流，优先寻找同出口、同模型的另一把 Key；本例 A 只有一把 Key，所以继续尝试 B。冷却影响后续候选是否可用，失败策略决定这次请求往哪个方向继续。

| 默认失败类型 | 下一步 | 冷却范围 |
| --- | --- | --- |
| 401 / 403 / 429 | 优先换同出口同模型的 Key，再尝试其他候选 | 当前 Key；多 Key 限流可升级为模型冷却 |
| 404 / 5xx / 超时 / 网络错误 | 优先换其他运行时渠道 | 当前出口的上游模型，按分类阈值触发 |
| 请求内容导致的 400 / 413 / 422 | 结束这次请求 | 通常不计入冷却；上下文超限等可识别情况可继续换候选 |
| 候选全部处于冷却 | 按设置等待最早恢复，或返回 503 与 `Retry-After` | 不另建一个“渠道整体冷却”计时器 |

管理员的检测规则可改变分类与冷却行为，不能只凭状态码猜最终策略。冷却到期后的探测由实际请求触发：只允许一个请求先试用该目标，成功后恢复，失败后重新冷却。

所有尝试共用首响应预算。假设将预算设为 10 秒，A 已消耗 7 秒，B 最多只能使用剩余约 3 秒；不会换一家供应商就重新获得 10 秒。非流式请求在预算内等待完整响应，流式请求在预算内等待首个有效输出。

如果请求包含多模态内容，且当前执行组候选耗尽，编排层才继续查看配置的多模态备用组；普通纯文本请求不会因为设置了备用组就自动进入它。对应实现见 [failover.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/router/failover.py)、[RequestDeadline](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/runtime_types.py) 和 [proxy_flow.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/proxy/proxy_flow.py)。完整参数见 [冷却与健康排序](../reference/configuration#冷却与健康排序)。

### B 成功后怎样返回与记账

B 返回 Chat 回复。Lens 先提取上游用量，再把回复转换为客户端使用的 Responses 格式，执行非流式响应钩子，记录成功结果并返回。

本次请求保留同一个日志 ID：请求组为 `daily-chat`，执行组为 `gpt-6.1-sol`，最终渠道为 B；`attempts` 中保留 A 的失败和 B 的成功。客户端不需要理解 A 的鉴权或 Chat 格式。请求观察插件在终态日志写入后，异步收到一次摘要。

转换只负责已支持的协议字段与事件，不能为上游补出不存在的模型能力。Chat、Responses、Anthropic 和 Gemini 对话协议通过统一结构连接；Embeddings、Images、Rerank 使用各自路径。工具、图像和流式行为需要按实际所用模型验证。转换入口见 [converters](https://github.com/dyedd/lens/tree/main/backend/app/gateway/converters)，日志写入见 [RequestLogger](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/request_logger.py)。

## 流式响应的边界

非流式请求先拿到完整结果再返回。流式请求会先检查可交付的起始内容，再持续向客户端发送数据，同时提取用量、结束标记和错误。需要转换时，每个协议事件经过统一的流式结构，再构造客户端事件。

| 阶段 | 能做什么 | 出错时的影响 |
| --- | --- | --- |
| 尚未向客户端交付响应 | 在共享预算内检测上游错误并继续选择候选 | 可以尝试下一成员 |
| 已经开始交付流式响应 | 持续转发或转换事件，按空闲超时等待下一块数据 | 不能撤回已发送内容，再用另一模型重放整个请求 |
| 流结束、报错或客户端断开 | 关闭上游响应，写入最终状态、用量和尝试记录，释放本次插件引用 | 日志可能为成功、失败或已取消；HTTP 200 本身不代表流成功结束 |

`stream_idle_timeout_seconds` 控制首个有效输出之后的相邻数据块等待时间。它与首响应预算分别处理“还没有结果”和“生成过程中停住”这两类情况。

对于本例使用的 Responses 流，Lens 捕获上游连接错误、超时或转换错误后，会在仍可发送的连接上输出 `event: error`，JSON 中的 `type` 为 `error`，随后结束流。已经发出的 HTTP 200 不会变成 502 或 504。上游原生错误事件也可能直接到达客户端；连接本身断开时，则未必还能收到完整错误事件。因此客户端应处理协议错误和连接异常，并确认是否收到正常终态，不能把“连接结束”一律当成成功。错误事件的构造见 [stream_error_frame](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/error_responses.py)，发送边界见 [proxy_upstream.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/proxy/proxy_upstream.py)。

流式响应的清理由 [FinalizingStreamingResponse](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/streaming/transport.py) 保证，流式终态及计费由 [streaming/logging.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/streaming/logging.py) 收口。界面排查步骤见 [查看用量与排查请求](../guide/monitoring)。

## 状态由谁保存

`AppState` 是一个 FastAPI 应用实例拥有的共享对象。它持有仓储、路由器、HTTP 连接池、插件注册表和计划任务运行器。请求不会各自新建整套这些资源，但会创建自己的日志上下文、失败账本和插件请求状态。

| 状态 | 所有者与生命周期 | 配置或进程变化时 |
| --- | --- | --- |
| 站点、Key、模型、组成员、设置、价格 | 数据库与对应仓储 | 持久化；后续请求按读取到的配置生成新计划 |
| 请求日志、用量与统计 | 请求日志仓储 | 持久化；清理与统计归档由计划任务处理 |
| 冷却、健康窗口、轮询游标、成功成员复用 | 当前进程的 `GatewayRouter` | 重启后重建；相关渠道配置改变时清理受影响状态 |
| 直连和代理 HTTP 连接池 | `AppState` | 按代理地址复用，应用关闭时释放 |
| 插件源文件 | `data/plugins/` 或指定目录 | 文件变化触发扫描与重新注册 |
| 插件启停和设置 | 数据库与插件注册表 | 新注册使用新设置；在途请求保留原扩展点快照 |
| 一次请求的候选、已尝试目标、截止时间 | 请求编排层 | 请求结束后释放 |
| 各插件的 `ctx.state` | 本次 `PluginRun` | 同一插件在这次请求的钩子间共享，不跨请求保存 |

例如 worker 1 遇到 A 限流，会更新自己的冷却状态；worker 2 不会因为共享了数据库就自动得到这条内存状态。因此，增加 worker 或部署多个副本，会增加独立的路由状态和连接池，不能把单进程的恢复探测理解为整个集群只探测一次。

插件注册表也属于当前进程。启停或保存设置会写入数据库，并立即刷新接收这次管理请求的进程；当前实现没有向其他进程广播配置变更。其他进程在重新启动、加载持久化插件配置后才取得这些值。目录监听和“重新扫描”只重新读取插件文件，不承担跨进程设置同步。对应入口见 [AppState](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/app_state.py) 和 [PluginRegistry](https://github.com/dyedd/lens/blob/main/backend/app/plugins/registry.py)。

插件回调也可能并发处理多个请求。每次请求的数据放入 `ctx.state`；跨请求资源放在注册时创建的对象中，并由插件自己处理并发和清理。详细生命周期见 [插件开发](./plugins#启停与热加载的生命周期)。

## 启动、关闭与后台任务

数据库迁移由 `lens setup`、`lens migrate` 或容器入口执行；`lens serve` 不替代迁移。应用启动阶段依次执行：

1. 校验签名密钥与时区，加载数据库里的运行设置。
2. 将上次中断遗留的进行中日志标为失败，避免它们一直显示“连接中”。
3. 扫描并注册插件，加载其持久化启停和设置。
4. 重新归组，确认当前配置对应的模型组成员。
5. 启动计划任务与插件目录监听，随后开始服务请求。

关闭时先停目录监听和计划任务，再交完插件观察队列、卸载插件，最后关闭 HTTP 客户端与数据库引擎。插件卸载发生在连接池和数据库关闭之前，使清理回调仍可使用这些资源。实现见 [lifecycle.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/service/lifecycle.py)。

渠道模型同步、价格同步、日志清理等任务通过同一个 `AppState` 使用仓储与插件能力，任务配置保存在数据库。日常操作见 [计划任务](../guide/maintenance#计划任务)。

每个进程都有计划任务运行器，但执行前要在数据库中取得该任务的租约：记录持有者和到期时间，只有取得租约的进程运行任务。在租约有效期间，其他进程不能再次领取同一任务；租约到期后可重新领取。这提供执行协调，但不等于外部副作用只会发生一次，插件任务仍应考虑重试或超出租约时长的情况。实现见 [cronjob_runner.py](https://github.com/dyedd/lens/blob/main/backend/app/gateway/cronjob_runner.py) 和 [CronjobStore](https://github.com/dyedd/lens/blob/main/backend/app/persistence/cronjob_store/store.py)。

## 修改功能时从哪里看

| 想修改的行为 | 先看 | 再核对 |
| --- | --- | --- |
| 新增管理端字段 | `models/` 输入输出类型、`service/admin/` | 持久化、备份导入导出、前端 API 类型与表单 |
| 改模型发现或同步 | `service/tasks/model_discovery.py`、`model_sync.py` | 站点模型保存、组归属、同步记录 |
| 改成员选择与故障转移 | `proxy/routing_plan.py`、`router/` | Key 与模型身份、冷却范围、上下文、尝试链 |
| 改协议支持 | `proxy_routes.py`、`converters/` | 原生路径、转换路径、流式事件、用量提取 |
| 改日志或费用 | `request_logger.py`、`streaming/logging.py` | 终态、取消、数据库写入、统计与备份 |
| 增加可选请求处理 | `plugins/contract.py`、`plugins/runtime.py` | 注册、启停、在途快照、超时与清理 |

表中的 `service/` 指 `backend/app/gateway/service/`。新功能应沿这些现有边界进入：路由器选择候选，转换器处理协议，请求编排串联阶段，仓储负责落盘。领域异常来自 `core/errors.py`；对外协议错误结构由 `gateway/service/error_responses.py` 生成。

## 构建与发布边界

管理界面由 `frontend/` 构建到 `backend/app/frontend/`，与后端一起进入应用 Docker 镜像。用户插件从挂载的数据目录加载。

文档由 `docs/` 独立构建到 `docs/.vitepress/dist/`，发布到 GitHub Pages。文档、截图、文档依赖与插件示例不进入应用镜像。三张机制图的 Mermaid 源文件保存在 `docs/diagrams/`，修改机制时同步更新正文与导出的 SVG。
