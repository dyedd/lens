# 系统设计与架构

Lens 的核心设计原则是 **控制面与执行面分离、客户端契约与上游拓扑解耦**。客户端只面向稳定的模型组名称与 Lens 协议入口；实际供应商选择、Key 轮换、协议转换、熔断冷却与成本核算全部在网关进程内闭环完成。

本页聚焦 **整体分层、领域模型、核心设计决策与状态边界**。运行时详细步骤请结合 [核心工作流解析](./workflow)，代码目录与扩展方式见 [源码结构与扩展指南](./source-guide)。

## 整体分层与进程模型

管理控制台（React SPA）与推理客户端访问同一个 FastAPI 应用实例，共享同一个 `AppState` 与数据库，但通过不同路由前缀与鉴权链路隔离：

[![管理界面通过管理服务保存配置，推理客户端通过请求编排访问路由器与上游，二者使用同一个数据库](/images/architecture.svg)](/images/architecture.svg)

| 分层 | 职责与核心抽象 | 关键边界 |
| --- | --- | --- |
| **API 与静态资源层** (`backend/app/api/`) | 装配 FastAPI 实例、CORS 中间件、GZip、异常映射与前端静态资源托管 | 不包含业务规则，只做路由注册与协议入口映射 |
| **网关编排层** (`backend/app/gateway/service/`) | 管理 `AppState`、认证鉴权、管理端 CRUD、请求编排（`proxy/`）、流式传输（`streaming/`）与后台任务（`tasks/`） | 持有请求级上下文（超时预算、隐私映射、日志上下文与尝试账本） |
| **路由与熔断层** (`backend/app/gateway/router/`) | `GatewayRouter` 组合 `RoutePlanner`（SWRR / Failover / 亲和）与 `HealthTracker`（`CooldownLedger` + `HealthScores`） | 纯内存状态机，不直接读写数据库 |
| **协议转换层** (`backend/app/gateway/converters/`) | 基于 Hub-and-Spoke（星型中间表示）在 OpenAI Chat / Responses / Anthropic / Gemini 间双向转换 | 无状态纯转换；同协议请求完全绕过此层直接透传 |
| **核心领域层** (`backend/app/core/`) | 纯函数规则：模型名推理后缀解析、协议可达矩阵、模型组匹配、参数/Header 规则求值、隐私规则、价格计算 | 不依赖 FastAPI 或异步会话，便于单元测试 |
| **持久化层** (`backend/app/persistence/`) | SQLAlchemy 异步 ORM、仓储（Repositories）、站点展平映射（`channel_store/`）、备份导入导出（`backup_store/`）、Alembic 迁移 | 唯一负责数据库读写与模型组归组落盘 |

## 领域模型与配置展开机制

界面里看到的“渠道”，在数据库中并非扁平单表，而是四层结构化实体；请求路由前，持久化层会通过 [`flatten_site`](https://github.com/dyedd/lens/blob/main/backend/app/persistence/channel_store/mapping.py) 将其展平为运行时可调度的 `ChannelConfig`。

```text
Site (站点：名称、启停、标签、代理、Headers、ParamOverride)
 ├── SiteBaseUrl (地址：url, kind = default | models | 协议专用)
 ├── SiteCredential (凭证：api_key, base_url_ids 作用域, rate_source 倍率源)
 └── SiteProtocolConfig (地址配置：绑定 base_url_id 与支持的协议列表)
       └── SiteDiscoveredModel (模型：model_name, protocol, enabled, context_window)

展开为运行时渠道 ChannelConfig (id = "{protocol_config_id}_{protocol}")
 └── 参与路由计划 RouteTarget (channel, credential_id, model_name, context_window, rate_multiplier)
```

这个设计解决了三个实际工程问题：

1. **目录拉取与推理出口分离**：`kind == "models"` 的 `SiteBaseUrl` 在 `flatten_site` 阶段即被过滤，永远不会成为推理候选，只供模型发现与同步使用。
2. **一匙多用不虚增权重**：数据库的组成员记录（`ModelGroupItemEntity`）通过 `(channel_id, credential_id, model_name)` 唯一定位；而在 `ROUND_ROBIN`（平滑轮询）排序时，`RoutePlanner._order_available` 会按 `(site_id, credential_id, model_name)` 合并同一把 Key 的多个协议/地址出口，使它**只占一个轮询席位**，其余出口留在后备链用于故障转移。
3. **归组结果预计算落盘**：模型归组（`reconcile_group_members`）在配置变更或同步时写入数据库，推理阶段直接读取已归组结果，不在高并发请求路径上反复扫描上游目录或全量正则匹配。

## 两层路由模型：执行组与别名组

Lens 用两种组类型解耦“对外暴露的模型名”与“实际供应商候选池”：

[![daily-chat 别名引用 gpt-6.1-sol 执行组，执行组按顺序保存 A-Key 和 B-Key 的两个上游成员](/images/routing-example.svg)](/images/routing-example.svg)

- **直接调度（执行组）**：`route_group_id == ""`。直接持有 `ModelGroupItem` 成员、分发策略（`FAILOVER` / `ROUND_ROBIN`）、默认上下文窗口以及多模态备用组列表（`fallback_group_ids`）。
- **别名（路由组）**：`route_group_id != ""`。不持有成员，仅引用一个执行组。`resolve_routing_plan` 禁止别名链式嵌套（别名引用别名会直接报错），并在日志中同时保留 `requested_group_name`（调用名）和 `resolved_group_name`（执行组名，用于计费与统计归因）。

## Hub-and-Spoke 协议转换设计

支持 $N$ 种对话协议两两互通如果手写点对点转换器需要 $N(N-1)$ 套代码；Lens 采用 **Unified IR（统一中间表示）** 将复杂度降至 $2N$：

```text
OpenAI Chat       ◀──┐                       ┌──▶ OpenAI Chat
OpenAI Responses  ◀──┼──▶  UnifiedRequest  ◀──┼──▶ OpenAI Responses
Anthropic         ◀──┼──▶  UnifiedResponse ◀──┼──▶ Anthropic
Gemini            ◀──┘     StreamEvent     └──▶ Gemini
```

### 设计要点

1. **同协议零损直通**：`needs_protocol_conversion(client, upstream)` 为 `False` 时（即协议相同），请求不进入 Spoke 解析/重建，仅做必要的轻量清理（如剥离跨供应商封印的推理签名 `strip_foreign_reasoning`、展开 Codex `additional_tools`）与规则覆盖后直接转发，完整保留 Prompt Cache 断点、`previous_response_id` 等原生语义。
2. **结构化能力降级（`capabilities.py`）**：
   - 目标协议不支持某个内容块时（如不支持部分媒体类型），按“每轮用户消息”统计：可表达的其余部分继续保留，仅当整轮消息被丢弃为空时才拒绝请求（`UnsupportedContentError`），避免静默丢消息或发送空消息导致上游报莫名其妙的 400。
   - Responses 的自由格式工具（`ToolKind.CUSTOM`）在其他协议中降级为单字段字符串函数 `{"input": "..."}`，并在响应与流式返回时通过 `tool_mapping` 逆向解包还原；带命名空间的工具名在扁平协议中展平为 `ns__tool` 并在响应时还原。
3. **封印推理状态安全隔离（`signatures.py`）**：Anthropic `thinking.signature`、Responses `reasoning.encrypted_content`、Gemini `thoughtSignature` 携带源协议 `origin` 与家族标记；仅在目标协议与模型家族匹配时重放，跨协议或跨家族切换时自动安全剥离或回退纯文本，避免上游因签名验签失败拒绝整个对话历史。
4. **非对话模态保持原生**：Embeddings、Images、Rerank 不进入对话 IR，直接走各自协议专用路径并支持独立计费字段（如图像按张计费）。

## 共享预算与失败边界

- **共享首响应预算（`RequestDeadline`）**：一次客户端请求只创建一次截止时间，该请求在主备切换中尝试 A、B、C 多个供应商时**共用**剩余 `first_token_timeout_seconds` 预算，防止故障转移累加出远超预期的挂起时间。
- **每次尝试独立重生成请求**：切换到备选渠道 B 时，总是基于原始输入（与隐私脱敏后请求）重新执行针对 B 的协议转换、参数规则、Compat 补丁（如 DeepSeek thinking / GLM reasoning 兼容）与 Header 规则，不会拿 A 改写过的请求体再去改写 B。
- **流式交付不可逆边界**：在收到首个有效响应块之前发生的上游错误或流前校验失败，可无感故障转移给下一成员；一旦已经向客户端发送 HTTP 200 头与首个数据块，后续中途断流或错误只能通过协议流错误帧（`stream_error_frame`）通知客户端并收敛日志状态。

## 状态所有权与多实例边界

`AppState` 由单个 FastAPI 应用进程持有（通过 `ContextVar` + `app.state.app_state` 绑定）。理解哪些状态在数据库、哪些在进程内存非常关键：

| 状态类型 | 归属位置 | 生命周期与多进程影响 |
| --- | --- | --- |
| 站点、Key、模型、模型组、设置、价格、网关密钥 | 数据库（SQLite / PostgreSQL） | 持久存储；每次请求实时读取配置并生效 |
| 请求日志、尝试链、统计归档 | 数据库 `request_logs` 等表 | 持久存储；重启时启动钩子自动将遗留 `connecting`/`streaming` 标为 `failed` |
| 冷却账本（`CooldownLedger`）、健康分窗口、SWRR 游标、故障亲和 | 当前进程的 `GatewayRouter` | **仅进程内存**；重启清空；多 worker / 多副本间不共享冷却与单探测锁 |
| 规则隐私历史映射（`PrivacyHistory`） | 当前进程内存（上限 256 条 / 16 MB / 1h） | **仅进程内存**；需要会话还原或多轮签名历史延续时建议单 worker 或粘性会话 |
| 后台计划任务租约（`lease_owner`, `lease_until`） | 数据库 `cronjobs` 表 | 跨进程互斥：多副本部署下同一时刻只有一个持有租约的进程执行任务 |
| 直连与按代理分组的 HTTP 连接池 | `AppState`（`httpx.AsyncClient`） | 按 `proxy_url` 缓存复用，应用退出 lifespan 时优雅关闭 |

## 构建与发布边界

- **应用镜像（`Dockerfile`）**：构建阶段独立编译 `frontend/` 至 `backend/app/frontend/`，再与后端打包进同一镜像；`docs/` 与截图通过 `.dockerignore` 排除，不进入应用容器。
- **文档站与版本检测（`docs/`）**：由 VitePress 独立构建到 `docs/.vitepress/dist/` 并发布至 GitHub Pages。正式 Release 工作流会同步更新 `docs/public/version.txt` 供在线 Lens 实例的 `version_check` 任务检测新版本。
