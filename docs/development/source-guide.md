# 源码结构与扩展指南

本页按模块映射 Lens 的前后端源码结构，说明核心文件职责与关键数据结构，并给出常见二次开发场景的“扩展配方”。

---

## 仓库顶层结构

```text
lens/
├── backend/
│   ├── alembic.ini                 # Alembic 数据库迁移配置
│   ├── pyproject.toml              # Python 包与 ruff / pytest 配置
│   ├── app/                        # 核心后端源码
│   └── tests/                      # API 与单元测试（遵循 lens-testing 规范）
├── frontend/
│   ├── src/                        # React 19 + TypeScript 控制台源码
│   └── package.json                # pnpm 脚本与依赖
├── docs/                           # VitePress 文档站（独立构建，不入应用镜像）
├── scripts/
│   ├── bump_version.py             # 同步 __init__.py 与 docs/public/version.txt 版本号
│   └── docker/                     # deploy.sh 与容器 entrypoint
├── .github/workflows/              # CI、镜像构建、自动发版、Pages 发布工作流
├── Dockerfile                      # 多阶段构建：先编 frontend，再打包 backend
├── docker-compose.yml              # 标准 Docker Compose 部署编排
└── docker-compose-1panel.yml       # 1Panel 专用网络与卷路径编排
```

---

## 后端源码逐模块解析（`backend/app/`）

### 1. 入口与 HTTP 装配（`api/` 与根目录）

| 文件 | 核心职责 |
| --- | --- |
| [`cli.py`](https://github.com/dyedd/lens/blob/main/backend/app/cli.py) | CLI 入口 `lens`：`setup`、`dev`（并行拉起 Uvicorn 与 Vite 代理）、`serve`、`migrate`、`seed-admin`、`db *` |
| [`main.py`](https://github.com/dyedd/lens/blob/main/backend/app/main.py) | ASGI 应用导出对象，供容器 Uvicorn 启动 |
| [`api/app.py`](https://github.com/dyedd/lens/blob/main/backend/app/api/app.py) | `create_app()`：装配 `lifespan`、`dynamic_cors_middleware`、`GZipMiddleware`、全局异常处理与路由表 |
| [`api/route_table.py`](https://github.com/dyedd/lens/blob/main/backend/app/api/route_table.py) | 唯一路由注册中心：区分 `/api/public/*`、`/api/admin/*` 与推理入口 `/v1/*`、`/v1beta/*` |
| [`api/ui_static.py`](https://github.com/dyedd/lens/blob/main/backend/app/api/ui_static.py) | SPA 静态资源托管与前端路由 history fallback |

### 2. 核心纯领域逻辑（`core/`）

这一层尽量保持“无 IO、纯函数”，便于测试与复用：

| 模块 | 职责说明 |
| --- | --- |
| `config.py` / `db.py` | 基于 `pydantic-settings` 读取 `LENS_*` 环境变量；异步 SQLAlchemy Engine/Session 工厂 |
| `errors.py` / `auth.py` | 领域异常层级（`RoutingError`、`ModelDiscoveryError`、`RequestCancelledError` 等）；JWT 签发与密码哈希 |
| `model_name_parser.py` | 解析 `model(effort)` / `model(budget)` 推理后缀，以及从各协议请求体提取思考强度 |
| `model_protocols.py` / `protocol_reachability.py` | 模型家族协议预选启发式规则；`CHAT_PROTOCOLS` 互通矩阵与 `can_reach_protocol` |
| `model_group_matching.py` / `model_group_status.py` | 模型组“包含 + 正则 + `or`/`and`”匹配与成员 `READY`/`INVALID` 状态求值 |
| `upstream_rules.py` | `RuleContext`、`RuleLayer`、`apply_param_rules`（点分路径 set/delete）与 `apply_header_rules`（正则条件 + 保护认证头） |
| `cooldown_rules.py` / `privacy_rules.py` | 自定义熔断检测规则编译；本地正则/词汇隐私扫描、超时保护与脱敏占位符生成 |
| `model_prices.py` / `context_windows.py` | 解析 LiteLLM 价格与上下文元数据；识别上下文超限报错文本 |

### 3. 协议转换器（`gateway/converters/`）

| 文件 | 职责说明 |
| --- | --- |
| `__init__.py` | `Spoke` Composition Root：注册 4 个对话协议的 6 个函数（request/response/stream 的 parse & build）及 `convert_request` / `convert_response` / `convert_stream_iterator` |
| `unified.py` / `unified_response.py` / `unified_stream.py` | 协议无关中间表示：`UnifiedRequest`（含 `Message`、`ContentPart`、`ToolDefinition`、`ReasoningIntent`、`Continuation`）、`UnifiedResponse`、`StreamEvent`（`BlockStart`/`BlockDelta`/`BlockStop` 等） |
| `spoke_chat.py` / `spoke_chat_stream.py` | OpenAI Chat Completions 解析与构建（含 SSE / NDJSON 流与 `chat_stream.py` 工具调用流修复） |
| `spoke_responses.py` / `responses_common.py` | OpenAI Responses API 解析与构建（含 `additional_tools` 提升、自定义工具、服务端工具） |
| `spoke_anthropic.py` | Anthropic Messages 解析与构建（含 `thinking`/`redacted_thinking`、`cache_control` 断点透传） |
| `spoke_gemini.py` | Gemini `generateContent` / `streamGenerateContent` 解析与构建（含 `thinkingConfig`、`thoughtSignature`） |
| `capabilities.py` / `signatures.py` | 无法直译内容块的按轮降级（`ContentDrops`）、自定义/命名空间工具包装还原、加密推理签名生命周期管理 |

### 4. 路由器与熔断器（`gateway/router/`）

| 文件 | 职责说明 |
| --- | --- |
| `gateway.py` | `GatewayRouter` 对外门面（加锁协调 `HealthTracker` 与 `RoutePlanner`，提供 `select`、`claim_target`、`record_*`、`snapshot`） |
| `routing.py` | `RoutePlanner`：上下文过滤、原生协议优先、端点优先级分组、故障亲和（`affinity`）、SWRR 平滑加权轮询 |
| `targets.py` | `RouteTarget`、`TargetKey` 构造与成员展平逻辑 |
| `cooldown.py` | `CooldownLedger` 状态机、指数退避、单探测租约（`claim_probe` / `release_probe`）与 `Retry-After` 解析 |
| `health.py` / `health_scores.py` | 组合冷却账本与滑动窗口成功率（`HealthScores`）；实现多 Key 限流自动升级为模型冷却（`_escalate_throttled_model`） |
| `failover.py` | `RetryAction`（`RETRY_KEY` / `RETRY_CHANNEL` / `TERMINAL`）与 `next_candidate` 分层候选检索 |

### 5. 网关服务与编排（`gateway/service/`）

| 路径 | 职责说明 |
| --- | --- |
| `app_state.py` / `app_context.py` / `lifecycle.py` | 进程单例 `AppState`（持有引擎、所有仓储、`GatewayRouter`、HTTP 连接池、`CronjobRunner`、`PrivacyHistory`、`active_requests`）及 FastAPI lifespan |
| `auth.py` | 管理员 JWT 登录限流保护（滑动窗口 + 并发信号量）与网关密钥校验 |
| `proxy_routes.py` | 各协议 FastAPI Handler（含 multipart 图像编辑解析、Anthropic system 消息提升、`/v1/models` 与 `/v1beta/models` 目录构造） |
| `proxy/proxy_flow.py` | 请求总编排：预算创建、隐私准备、权限校验、两层路由解析、重试循环、全冷却等待、终态收口 |
| `proxy/routing_plan.py` / `routing_request.py` | 执行组与别名解析；推理强度后缀注入目标请求体 |
| `proxy/proxy_attempt.py` / `proxy_upstream.py` | 单次尝试状态 `_AttemptRun`；请求构建、参数/兼容补丁、SSE 嗅探、流包装、错误分类映射 |
| `compat.py` | 厂商特定兼容补丁（如 DeepSeek 推理内容/工具调用补丁、GLM `output_config`/`thinking` 转换） |
| `streaming/` | `FinalizingStreamingResponse`、`capture.py`（流内用量/错误捕获）、`restore.py`（非流式还原 Anthropic SSE）、`privacy.py`（流式分片后隐私还原）、`logging.py`（后台流结束落库） |
| `tasks/` | 模型目录发现（`model_discovery.py`）、渠道模型同步（`model_sync.py`）、端点延迟探测（`endpoint_probe.py`）、站点模型测试（`site_model_probe.py`）、凭据倍率同步（`credential_rate_tasks.py`）、LiteLLM 同步、版本检测 |
| `admin/` 与 `foreign_site_import/` | 控制台 CRUD 服务及 6 种外部平台备份识别与解析器 |

### 6. 持久化层（`persistence/`）

| 路径 | 职责说明 |
| --- | --- |
| `entities.py` / `stats_entities.py` | 全部 SQLAlchemy ORM 表模型（站点 6 表、模型组 3 表、同步记录、正则表达式、设置、网关密钥、请求日志、统计归档、价格、计划任务） |
| `channel_store/` | 站点读写、`flatten_site` 展开与级联清理 |
| `backup_store/` | 全量配置与日志 JSON 序列化、导入事务覆盖与隐私清洗 |
| `cronjob_store/` | 计划任务调度计算与数据库租约抢占 |
| `repositories/` | 各领域仓储，其中 `group_reconcile.py` 负责自动归组、`request_log/` 拆分为读写/概览/多维归因/统计归档子模块 |
| `alembic/` | 历史迁移脚本；新增字段需在此新增修订 |

---

## 前端源码结构（`frontend/src/`）

控制台基于 **React 19 + TypeScript + TanStack Query + React Router + Tailwind CSS v4 + shadcn/ui**：

| 目录 / 文件 | 职责说明 |
| --- | --- |
| `AppProviders.tsx` / `main.tsx` | 挂载 Theme、I18n（中英双语）、QueryClient、AuthGuard 与路由 |
| `components/shell/` | `DashboardShell`、侧边栏导航与 `dashboardRoutes.ts`（定义 10 个主视图路径） |
| `components/screens/` | 主业务页面：`OverviewScreen`、`ModelHealthScreen`、`RequestsScreen`、`ChannelsScreen`、`GroupsScreen`、`ModelPricesScreen`、`CronjobsScreen`、`BackupsScreen`、`SettingsScreen`、`ApiKeysScreen`、`LoginScreen` |
| `components/settings/` | 各设置标签页组件与草稿校验逻辑（`settingsDraft.ts`、`PrivacySettingsSection.tsx`、`CircuitBreakerSettingsSection.tsx`、`config-transfer/` 等） |
| `components/model-test/` | 单个与批量模型测试弹窗及会话逻辑 |
| `lib/api/` | 强类型前端 API 客户端封装（`client.ts`、`sites.ts`、`groups.ts`、`requests.ts`、`settings.ts` 等） |

---

## 常见扩展配方（How-To）

### 1. 接入一个新的对话协议 Spoke

1. 在 `backend/app/models/protocols.py` 的 `ProtocolKind` 枚举中增加新协议。
2. 在 `backend/app/core/protocol_reachability.py` 将其加入 `CHAT_PROTOCOLS`（即自动获得与已有所有对话协议双向转换的能力）。
3. 在 `backend/app/gateway/converters/` 新增 `spoke_<name>.py`，实现请求、响应与流式的 parse/build 函数，并在 `converters/__init__.py` 的 `_spokes()` 中注册。
4. 在 `backend/app/gateway/service/proxy_routes.py` 与 `backend/app/api/route_table.py` 添加入口路由；在 `upstream_request.py` 补充上游路径与认证头构造；在 `backend/tests/` 添加请求与转换测试。

### 2. 新增一种外部平台渠道导入器

1. 在 `backend/app/models/foreign_imports.py` 的 `ForeignSiteFormat` 中加入格式标识。
2. 在 `backend/app/gateway/service/admin/foreign_site_import/detection.py` 添加格式特征识别函数。
3. 新建 `foreign_site_import/<platform>.py`，将外部备份解析为 `ParsedForeignSites`（输出标准 `SiteImportItem` 列表），并在 `preview.py` 的 `_PARSERS` 注册。
4. 在前端 `frontend/src/components/settings/config-transfer/ForeignImportCard.tsx` 的 `FORMAT_LABELS` 补充展示名称，并添加后端解析单测。

### 3. 新增一个可持久化的网关设置项

1. 在 `backend/app/persistence/settings_keys.py` 定义常量键，并在 `persistence/editable_settings.py` 与 `models/settings.py`（`RuntimeSettings`）注册类型与默认值校验。
2. 若影响路由行为，在 `AppState.apply_router_settings()` 同步下发到 `GatewayRouter`；若涉及备份导入导出，核对 `persistence/backup_store/` 的处理。
3. 在前端 `frontend/src/lib/api/settings.ts`、`components/settings/settingsDraft.ts` 与对应设置表单组件中添加 UI 控件，同步更新 [配置参考](../reference/configuration)。
