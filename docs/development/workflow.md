# 核心工作流解析

本页把 Lens 的端到端运行过程拆解为五条关键工作流：**配置展平与模型归组流**、**单次推理请求生命周期**、**熔断冷却与探测租约状态机**、**后台任务租约与生命周期流**、**本地开发与 CI/CD 发版工作流**。

---

## 工作流一：站点展平、模型同步与自动归组

当用户保存渠道、修改模型组、触发同步或启动应用时，配置如何转化为可供路由器消费的候选池：

```text
1. 站点配置落盘 (sites / site_base_urls / site_credentials / site_protocol_configs / site_discovered_models)
       │
       ▼
2. 模型发现与同步 (model_discovery.py / model_sync.py)
   ├── 仅处理 enabled && supports_model_listing 的站点
   ├── 优先选用 kind == "models" 的地址，否则使用协议对应地址（同源目录结果单次运行内缓存）
   ├── 支持多页游标拉取（最多 100 页，任一页失败抛 ModelCatalogIncompleteError 保留旧模型）
   └── channel_store.sync_upstream_models()：下线移除、在榜保留手动配置并更新上游上下文
       │
       ▼
3. 站点展平 (channel_store/mapping.py :: flatten_site)
   ├── 过滤 kind == "models" 地址
   ├── 按协议配置 × 协议列表展开为运行时 ChannelConfig (id = "{protocol_config_id}_{protocol}")
   └── 绑定凭证作用域（base_url_ids）与凭据倍率（rate_multiplier）
       │
       ▼
4. 模型组归组 (repositories/group_reconcile.py :: reconcile_group_members)
   ├── _join_matching_members()：
   │     ├── 清除已失效（INVALID）目标及不再匹配规则的自动成员（rule / placement）
   │     └── 保留手动成员（manual）；跳过已排除（excluded）的 (credential_id, model_name)
   └── _place_uncovered_models()：
         ├── 存在匹配同名执行组 → 加入该组
         ├── 无冲突且不在自动建组排除表 → 自动新建同名 FAILOVER 执行组并加入
         └── 其余模型 → 留在待分配列表（unplaced_models），记录 ModelSyncRun 报告
```

---

## 工作流二：一次推理请求的完整生命周期

以客户端请求 `POST /v1/responses`（`model: "daily-chat(high)"`，别名指向 `gpt-6.1-sol` 执行组，内含主渠道 A 与备用渠道 B）为例，完整代码流经 `proxy_routes.py` → `proxy_flow.py` → `routing_plan.py` → `proxy_attempt.py` → `proxy_upstream.py`：

[![客户端的一次 Responses 请求先调用 A，A 返回 429 后调用 B，B 成功后 Lens 转为 Responses 格式返回](/images/request-failover.svg)](/images/request-failover.svg)

### 阶段 1：入口鉴权与上下文初始化

1. **网关密钥认证**（`service/auth.py :: get_current_gateway_key`）：按 `Authorization: Bearer` → `x-api-key` → `x-goog-api-key` 顺序提取凭证，校验启用状态、过期时间与累计费用上限（`spent_cost_usd < max_cost_usd`）。失败直接返回 `401`，**不生成请求日志**。
2. **上下文准备**（`proxy_flow.py :: _prepare_proxy_context`）：并发加载运行时渠道列表与 `RuntimeSettings`，初始化请求级共享预算 `RequestDeadline`、同步路由器配置（`apply_router_settings`）、构建 `PrivacyContext`，并规范化透传 `User-Agent`。
3. **解析模型名与推理后缀**（`model_name_parser.py :: parse_model_name`）：从 `"daily-chat(high)"` 拆出基础模型名 `daily-chat` 与显式推理意图 `high`（若括号内容非法直接返回 `400 invalid_model`）。
4. **创建日志行与隐私预处理**：写入一条状态为 `connecting` 的 `request_logs` 记录，并在 `app_state.active_requests` 注册 `RequestCancellation`；加载会话历史映射并执行 `privacy.prepare()`（`block` 命中直接报错中止，不计入路由惩罚）；检查该网关密钥的模型权限白名单（`forbidden_model` → `403`）。

### 阶段 2：路由规划与候选筛选

1. **解析两层模型组**（`routing_plan.py :: resolve_routing_plan`）：按协议与组名查找组配置；若命中别名组（`route_group_id` 非空），加载目标执行组（禁止别名套别名）；过滤出 `READY` 且 `can_reach_protocol(item.protocol, client_protocol)` 为真的 `RouteTarget` 列表。
2. **路由器筛选与排序**（`router/routing.py :: RoutePlanner.select`）：
   - **上下文过滤**：根据估算请求 Token 数剔除已知上下文不足的候选（若无一满足则保留原池交由上游决定）；
   - **原生协议优先**：同一出口下若存在与客户端协议一致的原生目标，剔除同出口的转换目标；
   - **端点优先级与亲和**：按端点用途优先级分组；若处于故障亲和期内（`failover_affinity_seconds`），将上次救场成功的成员提至最前；
   - **策略排序**：`FAILOVER` 保持配置顺序；`ROUND_ROBIN` 按 `(site_id, credential_id, model_name)` 去重席位后用 SWRR 结合健康分选主候选；
   - **冷却目标排后**：将当前冷却中的目标按剩余冷却升序附在候选尾端，供必要时抢占单探测租约。

### 阶段 3：尝试循环、请求构造与故障转移

编排层在 `_run_route_attempts` 中循环挑选候选执行：

1. **检查预算与领取探测租约**：确认 `deadline.is_first_token_expired()` 未超时，调用 `next_candidate`（内部通过 `claim_target` 过滤未到期冷却目标，或为已到期目标签发独占探测租约）。
2. **生成针对当前目标的上游请求**（`proxy_attempt.py :: _prepare_attempt`）：
   - **协议转换或直通**：若 `needs_protocol_conversion`，调用 `convert_request` 经 Unified IR 转换并记录 `tool_mapping`；否则直通并执行 `lift_additional_tools`（Responses）与 `strip_foreign_reasoning`；
   - **参数覆盖与兼容层**：按 `全局 → 渠道 → 请求模型组` 顺序执行 `apply_param_rules`，再运行 `apply_deepseek_thinking_compat`、`apply_glm_chat_reasoning_compat` 与 `apply_reasoning_intent`；
   - **二次隐私准备与 Header 装配**：调用 `prepare_upstream_request` 注入上游鉴权头、白名单透传客户端头，并按 `全局 → 渠道 → 模型组` 叠加 Header 规则；校验 `max_request_body_bytes`（超限 `413` 直接终止不重试）。
3. **发送与异常处理**（`proxy_upstream.py :: execute_upstream_request`）：
   - 通过按代理地址复用的 `httpx.AsyncClient` 在 `first_token` 预算内发送；
   - 若上游报错，根据规则与状态码确定 `ErrorCategory`、`CooldownScope` 与 `RetryAction`：
     - `RETRY_KEY`（如 401/403/429）→ 优先选择**同渠道同模型的下一把 Key**；
     - `RETRY_CHANNEL`（如 404/5xx/超时/网络错误）→ 优先切换**其他渠道**；
     - `TERMINAL`（如普通 400/413/422 且非上下文超限）→ 立即写失败日志并返回客户端。
   - 若当前执行组耗尽且请求体包含多模态内容，`_iter_route_plans` 会继续按序解析 `fallback_group_ids`。
   - 若没有任何真实错误且全部目标均处于冷却中，检查 `failover_cooled_wait_seconds`：若允许等待且剩余预算充足，睡眠等待最早恢复目标后重新选路一次；否则丢弃空转日志并返回带 `Retry-After` 的 `503`。

### 阶段 4：响应交付、流式收口与计费

- **非流式**：在预算内读取响应 → 提取上游用量 → 跨协议转换（`convert_response`）与隐私还原（`privacy.restore`）→ 估算费用 → 写入 `RequestLogger.record_success` → 通知路由器 `record_success` 与 `note_success`。
- **流式**：通过 `_sniff_stream_response` 嗅探误标 Content-Type 的 SSE 响应 → 返回 `FinalizingStreamingResponse`（此时状态更新为 `streaming`）→ 流迭代器按 `stream_idle_timeout_seconds` 读取分块，依次经过 `repair_chat_tool_call_stream`、`convert_stream_iterator`、`restore_privacy_stream` → 流结束、报错或客户端断开后，由 `BackgroundTask` 调用 `_finalize_stream_request` 统一上报健康状态、释放探测租约并写入最终用量、费用与尝试链。

---

## 工作流三：熔断冷却、单探测租约与健康评分

状态机由 `HealthTracker`（`router/health.py`）协调 `CooldownLedger`（`router/cooldown.py`）与 `HealthScores`（`router/health_scores.py`）实现：

```text
               连续失败 >= threshold（或带 Retry-After）
[正常可用] ─────────────────────────────────────────────▶ [冷却中 cooled_until > now]
    ▲                                                            │
    │ 探测成功：清除状态                                           │ 时间到期 cooled_until <= now
    │ (且 started_revision >= failure_revision)                  ▼
[单探测租约 probe_lease_until] ◀──── 第一个请求抢占 ──── [待恢复探测]
    │                                （其余并发请求拒绝，继续转移他处）
    │ 探测失败（was_probe=True）
    └──────────────────────────────────────────────▶ [指数退避升级冷却]
```

- **两个独立故障域**：凭据域 `CredentialKey = (channel_id, credential_id, fault_protocol)` 与模型域 `ModelKey = (channel_id, model_name, fault_protocol)`。任意一域不可用则该组合不可用。
- **多 Key 限流升级**：当同一 `(channel_id, model_name, fault_protocol)` 在 `escalate_window_seconds` 内有至少 `escalate_threshold` 把不同 Key 触发 `RATE_LIMIT` 时，`_escalate_throttled_model` 自动对整个模型域写入冷却。
- **防止旧请求误解封**：每次失败会递增 `failure_revision`；只有起始修订号不早于最近一次失败的请求成功（`started_revision >= failure_revision`），才能清除该目标的冷却状态。

---

## 工作流四：启动自愈与后台计划任务租约

1. **应用启动生命周期**（`lifecycle.py :: lifespan`）：
   - 校验 `LENS_AUTH_SECRET_KEY` 与时区；
   - 初始化 HTTP 连接池并加载路由配置；
   - 调用 `fail_running_request_logs()` 将上次进程意外终止遗留的 `connecting` / `streaming` 日志标记为 `failed`；
   - 执行一次 `run_model_group_reconcile` 同步模型组成员；
   - 启动 `CronjobRunner`，随后开始接收请求。
2. **分布式安全租约**（`cronjob_runner.py` & `cronjob_store/store.py`）：
   - 每个任务执行前尝试在数据库 `cronjobs` 表原子更新 `lease_owner` 与 `lease_until`；
   - 只有成功拿到租约的进程才执行任务逻辑，避免多 worker 或多容器实例同时跑重复的模型同步或日志清理；
   - 应用退出时先停止 `CronjobRunner`、再关闭连接池与数据库引擎。

---

## 工作流五：本地开发与 CI/CD 发布流

仓库的工程自动化由 `.github/workflows/` 下的四套工作流协同完成：

1. **变更路径分流（`build.yml`）**：每次 Push / PR 首先由 `changes` Job 检查改动路径——若只改动了 `docs/**`、`*.md`、`screenshots/**` 或 `docs.yml`，直接跳过后端、前端与镜像构建。
2. **应用验证（`build.yml`）**：
   - `backend`：`compileall` → `ruff check` & `ruff format --check` → `pytest backend/tests` → 临时 SQLite 上运行 `app.cli db upgrade` + `alembic check`；
   - `frontend`：`biome ci .` → `pnpm test`（Vitest）→ `tsc --noEmit` → `pnpm build`；
   - `containers`：调用 `container-image.yml` 构建镜像（`main` 分支 Push 推送 `dev` 标签，正式 Release 推送 `latest` 与语义化版本标签）。
3. **自动发版（`release.yml`）**：每天 UTC `03:00` 检查自上个 `v*` Tag 以来的应用提交数；累计满 **5 个** 应用提交（手动触发只需 1 个）时，运行 `scripts/bump_version.py` 递增 patch 版本号、推送版本提交、构建多架构容器镜像、按 Conventional Commits 分类生成 Release Notes 并发布 GitHub Release，最后级联触发 `docs.yml`。
4. **文档发布（`docs.yml`）**：构建 VitePress 产物，同时查询 GitHub 最新正式 Release 写入 `.vitepress/dist/version.txt`，发布至 GitHub Pages，为所有在线 Lens 实例提供版本更新检测源。
