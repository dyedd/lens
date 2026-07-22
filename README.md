<p align="center">
  <img src="./ui/public/logo.svg" alt="Lens" width="88" height="88">
</p>

<h1 align="center">Lens</h1>

<p align="center">
  <a href="./README_EN.md">English</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white" alt="FastAPI 0.115+">
  <img src="https://img.shields.io/badge/Next.js-16-black?logo=nextdotjs" alt="Next.js 16">
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=111" alt="React 19">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License">
</p>

自托管多协议 LLM 网关，按站点、地址、凭证和协议组合管理多个模型供应商，并向客户端提供统一入口。

## 架构

```
┌──────────────────────────────────────────────────────────────────────┐
│ 客户端                                                               │
│ OpenAI SDK / Anthropic SDK / Gemini SDK / curl                       │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ Lens Base URL + sk-lens-...
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Lens Gateway                                                         │
│                                                                      │
│  多协议入口                                                          │
│  /v1/chat/completions                                                │
│  /v1/messages                                                        │
│  /v1/responses                                                       │
│  /v1/embeddings                                                      │
│  /v1/rerank                                                          │
│  /v1beta/models/{model}:generateContent                              │
│                                                                      │
│  请求解析                                                            │
│  - 校验网关 Key                                                       │
│  - 解析客户端协议和必填模型名                                         │
│  - 按入口协议和模型名匹配模型组，可指向另一个执行模型组               │
│                                                                      │
│  路由计划                                                            │
│  - 模型组成员：运行时渠道 + 凭证 + 上游模型                           │
│  - 路由策略：轮询 / 故障切换                                          │
│  - 协议转换：OpenAI Chat -> Anthropic / Responses                    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 管理配置                                                             │
│                                                                      │
│  站点                                                                │
│  ├─ Base URL：每个地址声明可用协议                                    │
│  ├─ 凭证：一个站点可维护多个 API Key                                  │
│  └─ 协议组合：Base URL + 默认凭证 + 协议列表 + 头/代理/参数/匹配规则  │
│                                                                      │
│  发现/手动模型                                                        │
│  - 模型挂在协议组合下，记录协议、凭证和上游模型名                     │
│  - 获取模型列表时优先走单次 /v1/models                                │
│                                                                      │
│  模型组                                                              │
│  - 声明入口协议、路由策略和可选执行模型组                             │
│  - 成员绑定到：运行时渠道 + 凭证 + 上游模型                           │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 候选展开与负载均衡                                                   │
│                                                                      │
│  运行时渠道 = 协议组合 + 单个协议                                     │
│  路由候选 = 运行时渠道 + 凭证 + 上游模型                              │
│                                                                      │
│  轮询：在候选之间平滑分发                                             │
│  故障切换：按模型组成员顺序尝试，失败后切到下一个凭证 / 渠道          │
│                                                                      │
│  冷却粒度                                                            │
│  401 / 403：冷却当前凭证；404 / 429 / 5xx / 超时 / 网络：冷却模型    │
│  同渠道其他模型继续可用；没有可用 Key + 模型绑定时渠道才整体不可用   │
│                                                                      │
│  请求日志                                                            │
│  记录生命周期、Token、成本、User-Agent、尝试链路和错误摘要            │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
        ┌──────────────┬──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────┐
   │ OpenAI  │    │Anthropic│    │ Gemini  │    │ 兼容服务 │
   └─────────┘    └─────────┘    └─────────┘    └──────────┘
```

## 功能

- 统一入口：一个 Base URL，一套网关 Key，支持 OpenAI / Anthropic / Gemini / Rerank 入口协议
- 站点管理：一个站点可配置多个 Base URL、多个凭证和多个协议组合，支持模型发现、手动模型和批量导入
- 模型组路由：按“运行时渠道 + 凭证 + 上游模型”组成候选，支持轮询、故障切换和执行模型组复用
- 协议转换：OpenAI Chat 可转发到 Anthropic Messages 或 OpenAI Responses
- 请求日志：记录协议、模型、延迟、Token、成本、User-Agent 和每次上游尝试链路
- 配置备份：导出/导入站点、模型组、设置、价格、定时任务、统计数据，可选包含网关 Key 和请求日志

## 截图

| 总览                                              | 请求日志                                                  |
| ------------------------------------------------- | --------------------------------------------------------- |
| <img src="./screenshots/overview.png" alt="总览"> | <img src="./screenshots/request-logs.png" alt="请求日志"> |

| 渠道                                              | 模型组                                                  |
| ------------------------------------------------- | ------------------------------------------------------- |
| <img src="./screenshots/channels.png" alt="渠道"> | <img src="./screenshots/model-groups.png" alt="模型组"> |

| 系统设置                                              | API 密钥                                              |
| ----------------------------------------------------- | ----------------------------------------------------- |
| <img src="./screenshots/settings.png" alt="系统设置"> | <img src="./screenshots/api-keys.png" alt="API 密钥"> |

| 定时任务                                                     | 备份恢复                                             |
| ------------------------------------------------------------ | ---------------------------------------------------- |
| <img src="./screenshots/scheduled-tasks.png" alt="定时任务"> | <img src="./screenshots/backups.png" alt="备份恢复"> |

## 快速开始

### Docker Compose（推荐）

```bash
mkdir lens && cd lens
curl -fsSLO https://raw.githubusercontent.com/dyedd/lens/main/scripts/docker/deploy.sh
sh deploy.sh
```

如需修改数据目录，只改 `volumes` 左侧的宿主机路径，右侧 `/app/data` 保持不变：

```yaml
volumes:
  - ./data:/app/data
```

启动：

```bash
docker compose pull
docker compose up -d
```

首次启动会创建管理员账号 `admin`，随机密码保存在容器数据目录的 `admin-password` 文件中。读取初始密码：

```bash
docker compose exec app cat /app/data/admin-password
```

访问 `http://127.0.0.1:3000`，登录后立即修改管理员密码，并删除数据目录中的 `admin-password` 文件。

### 本地构建镜像

```bash
sh scripts/docker/deploy.sh
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

`docker-compose.local.yml` 需要和 `docker-compose.yml` 放在同一目录。仓库中已提供该文件，会把镜像名改成 `lens:local` 并从当前源码构建。

如果在独立部署目录中本地构建，手动创建 `docker-compose.local.yml`：

```yaml
services:
  app:
    image: lens:local
    build:
      context: .
      dockerfile: Dockerfile
```

把项目源码放在同一目录，然后执行：

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

### 本地开发

需要 Python 3.11+、uv 和 pnpm。
下面的命令只在 `.env` 不存在时生成随机签名密钥，不会覆盖已有配置。

```bash
uv sync --extra dev --locked
cd ui && pnpm install && cd ..
uv run --no-sync python -c "import os, secrets; from pathlib import Path; path = Path('.env'); os.umask(0o077); path.exists() or path.write_text(f'LENS_AUTH_SECRET_KEY={secrets.token_hex(32)}\n', encoding='utf-8')"
uv run --no-sync lens db upgrade
uv run --no-sync lens seed-admin --username admin --generate-password
uv run --no-sync lens dev
```

本地开发默认端口：

- Next.js dev server：`http://127.0.0.1:3000`
- FastAPI 后端：`http://127.0.0.1:18080`

也可以分开启动：

```bash
uv run --no-sync lens serve

cd ui
pnpm dev
```

## 使用流程

### 1. 添加上游站点

进入 `/channels`，新建站点，配置 Base URL、凭证和协议组合，然后发现或手动添加模型。

- **Base URL**：一个站点可维护多个上游地址，并为每个地址声明支持的协议。
- **凭证**：一个站点可维护多个 API Key，后续路由可按凭证粒度切换。
- **协议组合**：绑定 Base URL、默认凭证和协议列表，可配置请求头、代理、参数覆盖和模型匹配规则。
- **模型**：模型挂在协议组合下，并可绑定到同站点不同凭证。

常见 Base URL：

| 上游类型        | Base URL 示例                               | 协议选择                             |
| --------------- | ------------------------------------------- | ------------------------------------ |
| OpenAI          | `https://api.openai.com`                    | OpenAI Chat / Responses / Embeddings |
| Anthropic       | `https://api.anthropic.com`                 | Anthropic                            |
| Gemini          | `https://generativelanguage.googleapis.com` | Gemini                               |
| NewAPI / Rerank | `https://newapi.example.com`                | Rerank（透传到 `POST /v1/rerank`）   |

### 2. 创建模型组

进入 `/groups`，新建模型组，选择入口协议，添加上游模型候选，选择路由策略：

- **轮询**：在模型组候选之间平滑轮询
- **故障切换**：优先使用前面的成员，失败后切到下一个凭证或渠道
- **执行组复用**：展示组可以指向另一个执行模型组，复用其候选和策略

**协议转换**：当前支持把 OpenAI Chat 上游加入 Anthropic 或 OpenAI Responses 模型组，运行时会自动转换。

### 3. 发放网关 Key

进入 `/api-keys`，新建 Key，复制 `sk-lens-...` 给客户端。

### 4. 客户端调用

客户端只需要：Lens Base URL + 网关 API Key + 模型组名称。

## 技术栈

| 层   | 技术                                                            |
| ---- | --------------------------------------------------------------- |
| 后端 | Python 3.11+、FastAPI、SQLAlchemy、Alembic、SQLite / PostgreSQL |
| 前端 | Next.js 16、React 19、TypeScript、TanStack Query、shadcn/ui     |

## 配置

### 后端环境变量

| 变量                             | 默认值                               | 说明                                                               |
| -------------------------------- | ------------------------------------ | ------------------------------------------------------------------ |
| `LENS_DATABASE_URL`              | `sqlite+aiosqlite:///./data/data.db` | 数据库连接；Docker 镜像使用 `/app/data/data.db`                    |
| `LENS_AUTH_SECRET_KEY`           | 无（必填）                           | JWT 签名密钥，UTF-8 编码后至少 32 字节；Docker 部署脚本写入 `.env` |
| `LENS_PORT`                      | 本地 `18080` / Docker `3000`         | 服务监听端口；Docker Compose 同时用作宿主机与容器端口映射          |
| `LENS_MAX_CONNECTIONS`           | `200`                                | 每个直连或代理连接池的最大连接数，修改后需要重启                   |
| `LENS_MAX_KEEPALIVE_CONNECTIONS` | `50`                                 | 每个直连或代理连接池的最大空闲连接数，修改后需要重启               |

### 网关设置

在 `/settings` 页面修改：

| 设置键                        | 默认值     | 说明                                                                                                   |
| ----------------------------- | ---------- | ------------------------------------------------------------------------------------------------------ |
| `auth_access_token_minutes`   | `720` 分钟 | 新签发登录令牌的有效期；范围 `1`–`525600`                                                                  |
| `first_token_timeout_seconds` | `180` 秒   | 首个可交付响应的共享预算：流式请求等待首个有效输出，非流式请求等待完整响应；范围 `0`–`86400`，`0` 不限制 |
| `stream_idle_timeout_seconds` | `180` 秒   | 流式请求首个有效输出后，相邻上游数据块的最长等待；范围 `0`–`86400`，`0` 不限制                           |
| `max_request_body_bytes`      | `32000000` | 发送到上游的请求体上限；`0` 不限制                                                                      |

#### 冷却与健康排序

冷却首先作用于能够被错误证据直接定位的资源。`401` / `403` 冷却当前 Key；`404`、`429`、`5xx`、上游 `408`、网关超时和网络错误冷却当前实际上游模型。同渠道其他模型或其他 Key 仍可参与路由。除 `401` / `403` / `404` / `408` / `429` 外的普通 `4xx` 通常只说明当前请求不可接受，不计入冷却。`429` / `503` 的标准 `Retry-After` 会立即触发当前模型冷却，并在最大冷却限制内优先于分类默认值；`0` 表示立即恢复。

渠道没有独立的冷却计时器。对每个已启用的“Key + 模型”绑定：

```text
绑定可用时间 = max(Key 冷却截止时间, 模型冷却截止时间)
渠道可用      = 存在至少一个绑定，其可用时间 <= 当前时间
渠道恢复时间  = min(所有绑定的可用时间)
```

渠道只在没有任何启用的“Key + 模型”绑定可用时整体不可用。所有配置模型均在冷却、所有启用 Key 均在冷却是两个常见情况；稀疏绑定也可能因部分模型与部分 Key 的组合冷却而耗尽。任一绑定恢复后渠道立即恢复，不再额外增加渠道级冷却。

每个错误类别达到阈值后按指数退避计算冷却。同一轮冷却期间返回的并发失败不会继续放大退避：

```text
首次冷却 = min(分类初始冷却, 最大冷却)
后续冷却 = min(上次冷却 × 退避倍率, 最大冷却)
```

同类失败尚未触发冷却时，失败窗口按相邻失败间隔计算；完成一次冷却后，从目标恢复可用的时刻开始计算稳定期。只有目标持续超过该窗口没有再次失败，连续失败计数和退避状态才会重新开始。因此目标在冷却结束后立即再次失败时会正常升级退避，而不会被冷却等待时间本身重置。

`0` 秒的分类初始冷却会关闭该类别的冷却并清除其连续失败计数与退避状态；最大冷却为 `0` 会关闭全部自动冷却。一次成功请求只重置当前模型及实际使用的 Key，冷却开启前已经在途的旧请求成功不会解除更新的冷却。同一轮冷却期间的并发失败不延长冷却或放大退避，但仍会阻止更早的在途成功清除新失败。冷却到期后目标直接恢复为可选候选，不额外执行半开探测。

健康分使用按“渠道 + 实际模型”统计的滑动窗口。`ROUND_ROBIN` 将健康分作为平滑加权轮询的权重，并优先使用较健康的失败后备选；`FAILOVER` 保持模型组配置顺序，不被健康分重排：

```text
置信度 = min(1, 窗口样本数 / 完整置信样本数)
健康分 = 1 - 失败率 × 最大惩罚比例 × 置信度
```

冷却和健康窗口是当前 Lens 进程内的运行时状态：进程重启后清空，多 worker 或多实例之间不共享。更新同 ID 的 Key 内容会清除该 Key 的旧状态；更换渠道端点、协议或影响上游请求的渠道配置会清除该渠道状态；全局代理或上游 Header 规则变化会清除全部运行时冷却与健康窗口。

| 设置键                                      | 默认值 | 说明 |
| ------------------------------------------- | ------ | ---- |
| `circuit_breaker_threshold`                 | `3`    | `5xx` 连续失败阈值，正整数；带 `Retry-After` 的 `503` 立即触发冷却 |
| `circuit_breaker_failure_window_seconds`    | `300`  | 未冷却时的相邻同类失败窗口，也是冷却结束后的无失败稳定期；范围 `1`–`604800`，与健康评分窗口独立 |
| `circuit_breaker_timeout_threshold`         | `2`    | 上游 `408` 或网关超时的连续失败阈值，正整数 |
| `circuit_breaker_network_threshold`         | `2`    | 网络错误连续失败阈值，正整数 |
| `circuit_breaker_cooldown`                  | `60`   | `5xx` 初始冷却秒数，范围 `0`–`604800` |
| `circuit_breaker_auth_cooldown`             | `300`  | `401` / `403` 的 Key 初始冷却秒数，范围 `0`–`604800` |
| `circuit_breaker_not_found_cooldown`        | `300`  | `404` 的模型初始冷却秒数，范围 `0`–`604800`；无法确认更大故障域时只影响当前模型 |
| `circuit_breaker_rate_limit_cooldown`       | `60`   | `429` 的模型初始冷却秒数，范围 `0`–`604800` |
| `circuit_breaker_timeout_cooldown`          | `60`   | 上游 `408` 或网关超时的模型初始冷却秒数，范围 `0`–`604800` |
| `circuit_breaker_network_cooldown`          | `60`   | 网络错误的模型初始冷却秒数，范围 `0`–`604800` |
| `circuit_breaker_backoff_multiplier`        | `2`    | 后续冷却倍率，范围 `1`–`10` |
| `circuit_breaker_max_cooldown`              | `600`  | 所有自动冷却的严格上限秒数，范围 `0`–`604800`；`0` 关闭自动冷却 |
| `health_scoring_enabled`                    | `true` | 是否启用健康排序 |
| `health_window_seconds`                     | `300`  | 按模型统计的滑动窗口长度，范围 `1`–`604800` |
| `health_penalty_weight`                     | `0.5`  | 最大健康惩罚比例，范围 `0`–`1` |
| `health_min_samples`                        | `10`   | 达到完整置信度所需的样本数，正整数 |

### Docker Compose

| 变量                   | 默认值 | 说明                                                          |
| ---------------------- | ------ | ------------------------------------------------------------- |
| `LENS_PORT`            | `3000` | 容器监听端口与宿主机映射端口（同一值）                        |
| `LENS_SKIP_DB_UPGRADE` | `0`    | 容器启动时设为 `1` 可跳过自动数据库迁移；需自行确保结构已升级 |

### PostgreSQL 配置

PostgreSQL 连接串格式：

```
postgresql+psycopg://用户名:密码@主机:端口/数据库名
```

示例：

```bash
LENS_DATABASE_URL=postgresql+psycopg://lens:password@postgres.example.com:5432/lens
```

**1Panel 等容器化环境配置技巧**：

如果 Lens 和 PostgreSQL 部署在同一台服务器，推荐把两个容器放到同一个 Docker 网络（例如 1Panel 的 `1panel-network`），然后用 PostgreSQL 容器名作为主机名：

```bash
LENS_DATABASE_URL=postgresql+psycopg://lens:password@postgresql:5432/lens
```

这里第一个 `lens` 是数据库用户名，最后一个 `lens` 是数据库名；`postgresql` 是 PostgreSQL 容器名，需要按实际容器名调整。

**SQLite 适合本地测试和轻量部署，生产环境或高并发场景建议使用 PostgreSQL。**

## 数据库迁移

```bash
uv run lens db upgrade  # 升级到最新
uv run lens db downgrade  # 回退一步
uv run lens db revision -m "describe your change"  # 生成新迁移
```

从 SQLite 切换到 PostgreSQL：在 `/backups` 导出配置 → 修改 `LENS_DATABASE_URL` → 启动 Lens → 导入配置。

## 客户端接入

<details>
<summary>OpenAI SDK (Python)</summary>

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:3000/v1",
    api_key="sk-lens-...",
)

completion = client.chat.completions.create(
    model="your-model-group",
    messages=[{"role": "user", "content": "hello"}],
)
print(completion.choices[0].message.content)
```

</details>

<details>
<summary>Anthropic SDK (Python)</summary>

```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://127.0.0.1:3000",
    api_key="sk-lens-...",
)

message = client.messages.create(
    model="your-anthropic-group",
    max_tokens=256,
    messages=[{"role": "user", "content": "hello"}],
)
print(message.content[0].text)
```

</details>

<details>
<summary>OpenAI Chat (curl)</summary>

```bash
curl http://127.0.0.1:3000/v1/chat/completions \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model-group",
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

</details>

<details>
<summary>Anthropic Messages (curl)</summary>

```bash
curl http://127.0.0.1:3000/v1/messages \
  -H "x-api-key: sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-anthropic-group",
    "max_tokens": 256,
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

</details>

<details>
<summary>OpenAI Responses (curl)</summary>

```bash
curl http://127.0.0.1:3000/v1/responses \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-responses-group",
    "input": "hello"
  }'
```

</details>

<details>
<summary>OpenAI Embeddings (curl)</summary>

```bash
curl http://127.0.0.1:3000/v1/embeddings \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-embedding-group",
    "input": "hello world"
  }'
```

</details>

<details>
<summary>Rerank (curl)</summary>

```bash
curl http://127.0.0.1:3000/v1/rerank \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-rerank-group",
    "query": "What is the capital of France?",
    "documents": [
      "Paris is the capital of France.",
      "Berlin is the capital of Germany.",
      "Madrid is the capital of Spain."
    ],
    "top_n": 3,
    "return_documents": true
  }'
```

请求体透传到上游 `/v1/rerank`（如 NewAPI、Jina、Cohere 等兼容服务）。响应原样返回，包含 `results[*].relevance_score / index / document`。

</details>

<details>
<summary>Gemini (curl)</summary>

```bash
curl "http://127.0.0.1:3000/v1beta/models/your-gemini-model:generateContent" \
  -H "x-goog-api-key: sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [
      {
        "role": "user",
        "parts": [{"text": "hello"}]
      }
    ]
  }'
```

</details>

<details>
<summary>Claude Code</summary>

```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:3000
ANTHROPIC_AUTH_TOKEN=sk-lens-...
ANTHROPIC_MODEL=your-anthropic-group
ANTHROPIC_SMALL_FAST_MODEL=your-anthropic-group
```

</details>

<details>
<summary>Codex</summary>

`~/.codex/config.toml`：

```toml
model = "your-model-group"
model_provider = "lens"

[model_providers.lens]
name = "Lens"
base_url = "http://127.0.0.1:3000/v1"
```

`~/.codex/auth.json`：

```json
{
  "OPENAI_API_KEY": "sk-lens-..."
}
```

</details>

## 致谢

- [bestruirui/octopus](https://github.com/bestruirui/octopus)
- [cita-777/metapi](https://github.com/cita-777/metapi)
- [caidaoli/ccLoad](https://github.com/caidaoli/ccLoad)
- [Linux DO 社区](https://linux.do/)

## License

MIT
