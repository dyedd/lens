# 环境变量与网关设置

进程启动参数由 **环境变量**（`.env`）控制，修改后需重启进程或重建容器；业务策略与路由阈值由 **网关设置** 控制，保存在数据库 `settings` 表中，在管理界面修改后即刻生效。

## 后端与容器环境变量

| 变量名 | 默认值 | 说明 |
| --- | --- | --- |
| `LENS_AUTH_SECRET_KEY` | 无（**必填**） | JWT 签名密钥，UTF-8 编码长度需至少 32 字节（推荐 64 位十六进制） |
| `LENS_DATABASE_URL` | `sqlite+aiosqlite:///./data/data.db` | 数据库连接串；Docker 镜像内默认指向 `/app/data/data.db` |
| `LENS_PORT` | 本地 `18080` / Docker `3000` | 服务监听端口；Docker Compose 同时用作宿主机与容器端口映射 |
| `LENS_MAX_CONNECTIONS` | `200` | 每个直连或代理 HTTP 连接池允许的最大并发连接数 |
| `LENS_MAX_KEEPALIVE_CONNECTIONS` | `50` | 每个直连或代理 HTTP 连接池保留的最大长连接数 |
| `LENS_SKIP_DB_UPGRADE` | `0` | 仅容器入口脚本读取：设为 `1` 时跳过启动自动迁移与初始管理员密码生成 |
| `LENS_DATA_DIR` | `/app/data` | 非 SQLite 数据库场景下 `lens` CLI 写入初始密码文件等数据文件的目录 |

### PostgreSQL 连接串格式

```dotenv
LENS_DATABASE_URL=postgresql+psycopg://用户名:密码@主机:端口/数据库名
```

- 密码若包含 `@`、`#`、`%` 等特殊字符请先做 URL 编码。
- 在 1Panel 或同宿主机 Docker Compose 场景中，将两个容器加入同一网络（如 `1panel-network`），主机名直接填写 PostgreSQL 容器名（例如 `postgresql:5432`）。

## 网关通用设置

可在 **设置 → 常规** 与 **设置 → 网关** 页面或通过管理 API 修改（完整键定义见 [`settings_keys.py`](https://github.com/dyedd/lens/blob/main/backend/app/persistence/settings_keys.py)）：

| 设置键 | 默认值 | 说明 |
| --- | --- | --- |
| `site_name` | `"Lens"` | 控制台展示名称 |
| `site_logo_url` | `""` | 自定义 Logo 地址（留空使用内置图标） |
| `time_zone` | 系统本地时区 | 全局与计划任务运行参考时区 |
| `stats_time_zone` | 同 `time_zone` | 概览按日聚合使用的统计时区 |
| `auth_access_token_minutes` | `720` 分钟 | 新签发管理员 JWT 的有效期，范围 `1`–`525600` |
| `proxy_url` | `""` | 全局上游 HTTP/SOCKS 代理地址 |
| `cors_allow_origins` | `[]` | 允许跨域访问的 Origin 列表 |
| `first_token_timeout_seconds` | `180` 秒 | 首个可交付响应的共享总预算（流式等待首个有效块；非流式等待完整响应），范围 `0`–`86400`，`0` 为不限制 |
| `stream_idle_timeout_seconds` | `180` 秒 | 流式响应首块输出后，相邻上游数据块的最长等待时间，范围 `0`–`86400`，`0` 为不限制 |
| `max_request_body_bytes` | `32000000` | 发往上游请求体字节上限（含 multipart），超出返回 `413`；`0` 为不限制 |
| `relay_log_body_enabled` | `false` | 是否在请求日志中保存请求体与响应体 |
| `relay_log_keep_enabled` | `true` | 是否启用定期清理过期请求日志 |
| `relay_log_keep_period` | `7` 天 | 请求日志保留天数，范围 `1`–`36500` |
| `upstream_headers_config` | `{"rules":[]}` | 全局上游请求头规则（支持 `append`/`override`/`remove` 及路径/模型/协议正则匹配，认证头受保护不可改写） |
| `upstream_param_override_config` | `{"rules":[]}` | 全局上游请求体参数覆盖规则（支持 `set`/`delete` 点分路径，禁止修改 `model`） |

## 冷却与健康排序

可在 **设置 → 故障转移** 修改（详细状态机见 [核心工作流 · 熔断冷却与探测租约](../development/workflow#工作流三：熔断冷却、单探测租约与健康评分)）。

### 错误分类与故障域

1. **自定义检测规则优先（`cooldown_detection_rules`）**：按优先级从高到低匹配 `status_code` 与 `body_regex`，命中后可显式指定错误类别（`category`）、冷却作用域（`scope`：`key`/`model`/`channel`）、动作（`action`：`retry_key`/`retry_channel`/`terminal`）和冷却时长。
2. **默认状态码分类**：
   - `401` / `403` / `429` → 作用于 **当前 Key**（默认先尝试同出口同模型的下一把 Key）；
   - `404` / `408` / `5xx` / 网关超时 / 网络错误 → 作用于 **当前出口的上游模型**（优先切换其他可用渠道）；
   - 普通请求错误（`400` / `413` / `422`）→ 通常立即结束请求且不计入冷却；若识别为上下文窗口超限，则允许继续尝试更大窗口候选。
3. **多 Key 限流自动升级**：同一渠道同一模型在 `circuit_breaker_escalate_window_seconds`（默认 60 秒）内有 `circuit_breaker_escalate_threshold`（默认 2 把）及以上 Key 触发 429 限流时，自动升级为该模型冷却，避免每把 Key 重复撞墙。
4. **`Retry-After` 优先**：上游返回 `429` 或 `503` 且带有标准 `Retry-After` 响应头时，立即按该时长（受 `circuit_breaker_max_cooldown` 上限约束）触发对应故障域冷却；`0` 表示立即恢复。

### 渠道可用性与指数退避计算

渠道本身没有独立的整体冷却计时器，而是由所有已启用“Key + 模型”绑定共同决定：

```text
绑定可用时间 = max(渠道整体冷却截止时间, 模型冷却截止时间, Key 冷却截止时间)
渠道可用      = 存在至少一个可用时间 <= 当前时间的绑定
渠道恢复时间  = min(所有绑定的可用时间)
```

达到连续失败阈值后按指数退避计算冷却（同一轮冷却期间的并发失败不会重复叠加退避）：

```text
首次冷却 = min(分类初始冷却, 最大冷却)
后续冷却 = min(上次冷却 × 退避倍率, 最大冷却)
```

- 将某类别的初始冷却设为 `0` 会禁用该类别的自动冷却；将 `circuit_breaker_max_cooldown` 设为 `0` 会关闭全部自动冷却。
- 健康评分基于滑动窗口成功率计算，仅在 `ROUND_ROBIN` 策略下作为平滑加权轮询（SWRR）权重；`FAILOVER` 始终保持模型组配置顺序：

```text
置信度 = min(1, 窗口样本数 / health_min_samples)
健康分 = 1 - 失败率 × health_penalty_weight × 置信度
```

> [!NOTE]
> 冷却状态与健康窗口保存在当前进程的 `GatewayRouter` 内存中：进程重启后清空，多 worker / 多实例之间不共享。更新 Key 内容、修改渠道配置或修改全局代理/Header 规则会自动清理受影响的运行时状态。

### 故障转移设置键一览

| 设置键 | 默认值 | 说明 |
| --- | --- | --- |
| `circuit_breaker_threshold` | `3` | `5xx` 连续失败阈值（正整数）；带 `Retry-After` 的 `503` 立即触发 |
| `circuit_breaker_timeout_threshold` | `2` | 上游 `408` 或网关超时的连续失败阈值 |
| `circuit_breaker_network_threshold` | `2` | 网络连接错误的连续失败阈值 |
| `circuit_breaker_failure_window_seconds` | `300` | 相邻同类失败统计窗口与冷却恢复后的无失败稳定期（`1`–`604800`） |
| `circuit_breaker_cooldown` | `60` | `5xx` 初始冷却秒数（`0`–`604800`） |
| `circuit_breaker_auth_cooldown` | `300` | `401` / `403` 的 Key 初始冷却秒数 |
| `circuit_breaker_not_found_cooldown` | `300` | `404` 的模型初始冷却秒数 |
| `circuit_breaker_rate_limit_cooldown` | `60` | `429` 的 Key 初始冷却秒数 |
| `circuit_breaker_timeout_cooldown` | `60` | 超时错误的模型初始冷却秒数 |
| `circuit_breaker_network_cooldown` | `60` | 网络错误的模型初始冷却秒数 |
| `circuit_breaker_backoff_multiplier` | `2` | 指数退避倍率（`1`–`10`） |
| `circuit_breaker_max_cooldown` | `600` | 自动冷却严格上限秒数（`0`–`604800`，`0` 关闭自动冷却） |
| `circuit_breaker_escalate_threshold` | `2` | 同窗口内触发限流的不同 Key 达到此数量时升级为模型冷却（`0` 关闭，最大 `100`） |
| `circuit_breaker_escalate_window_seconds` | `60` | 多 Key 限流升级统计窗口（最大 `604800`） |
| `failover_cooled_wait_seconds` | `0` | 全部候选均处于冷却时，请求最长等待最早恢复目标的秒数（`0` 表示直接返回带 `Retry-After` 的 `503`） |
| `failover_affinity_seconds` | `30` | 故障切换成功后短期内优先复用成功成员的秒数（`0` 关闭，最大 `3600`） |
| `health_scoring_enabled` | `true` | 是否在轮询模式启用健康分加权 |
| `health_window_seconds` | `300` | 健康分滑动统计窗口秒数 |
| `health_penalty_weight` | `0.5` | 最大失败惩罚权重（`0`–`1`） |
| `health_min_samples` | `10` | 达到完整置信度所需的最小样本数 |

## 规则隐私（`privacy_config`）

`privacy_config` 默认关闭，可在 **设置 → 隐私** 配置：

```json
{
  "enabled": false,
  "categories": ["secrets", "personal"],
  "action": "mask",
  "words": [],
  "regex_rules": [],
  "exceptions": []
}
```

| 字段 | 规范与限制 |
| --- | --- |
| `enabled` | 是否启用规则隐私 |
| `categories` | `secrets`（常见 API Key、私钥、JWT、含密连接串及中英文密码/密钥赋值）；`personal`（邮箱、手机号、校验有效的中国身份证号、Luhn 银行卡号） |
| `action` | `mask`（替换为占位符并在响应还原）、`warn`（原文发往上游但清理日志）、`block`（本地拒绝请求） |
| `words` | 精确匹配自定义词，区分大小写；最多 `100` 项，每项最多 `256` 字符 |
| `regex_rules` | `[{"pattern": "..."}]`；最多 `20` 项，每条最多 `512` 字符；使用 Python 正则带超时保护，拒绝非法或可匹配空串的表达式 |
| `exceptions` | 精确匹配的例外词；最多 `100` 项，每项最多 `256` 字符；完整落入例外词的命中会被忽略 |

### 扫描边界与运行时约束

- **扫描与保留边界**：处理文本正文、`system`/`instructions`、工具描述/参数/结果以及 Embeddings/Rerank/Images 文本输入；协议骨架字段（模型名、工具名、调用 ID、schema、枚举、媒体 URL 与二进制附件）保持原样；上游认证仍使用渠道真实 Key。
- **单请求保护限制**：单字段文本上限 `2,000,000` 字符，单请求最多保留 `4,096` 条映射，原值总量上限 `2,000,000` 字节；超时或超限会直接返回隐私错误并中止上游请求。
- **进程内历史缓存**：用于跨轮次恢复或 `previous_response_id`/签名引用校验；单进程最多保留 `256` 个引用、总量 `16 MB`、单个引用保留 `1` 小时。需要会话恢复连续性的多轮调用建议固定到同一 worker（并可传 `x-lens-session-id` 头，最长 `256` 字符）。
- **预览接口**：管理员可调用 `POST /api/admin/settings/privacy/preview`（请求体 `{"text": "...", "config": {...}}`，最多 `100,000` 字符）验证规则，不修改运行时状态也不记录日志。
