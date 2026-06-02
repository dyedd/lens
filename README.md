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

自托管 LLM 网关，统一管理多个模型供应商。

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
│  入口协议                                                            │
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
│  - 按入口协议和模型名匹配模型组                                       │
│                                                                      │
│  路由计划                                                            │
│  - 模型组成员：渠道 + 密钥 + 上游模型                                 │
│  - 路由策略：轮询 / 故障切换                                          │
│  - 协议转换：OpenAI Chat -> Anthropic / Responses                    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 候选展开                                                             │
│                                                                      │
│  渠道协议配置                                                        │
│  协议 + 地址来源 + 绑定密钥                                           │
│                                                                      │
│  运行时候选                                                          │
│  运行候选 = 渠道 + 密钥 + 上游模型                                    │
│                                                                      │
│  示例                                                                │
│  模型组成员: 稳定分组 / gpt-5.5                                      │
│      ├─ 渠道 A / 地址 1 / 福利 key  / gpt-5.5                        │
│      ├─ 渠道 A / 地址 1 / 稳定 key  / gpt-5.5                        │
│      └─ 渠道 B / 备用 key  / gpt-5.5                                 │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 负载均衡与故障转移                                                   │
│                                                                      │
│  轮询：在 key 级候选之间平滑分发                                     │
│  故障切换：按模型组成员顺序尝试，失败后切到下一个 key / 渠道          │
│                                                                      │
│  冷却粒度                                                            │
│  401 / 403 / 429：冷却单个密钥，优先换同站点其他候选                │
│  5xx / 超时 / 网络错误：冷却整个渠道，切到其他可用候选                │
│                                                                      │
│  请求日志                                                            │
│  尝试链路记录渠道、密钥、上游模型、状态和耗时                         │
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

- 统一入口：一个 Base URL，一套 API Key，支持 OpenAI / Anthropic / Gemini 协议
- 负载均衡：在“渠道 + 密钥 + 上游模型”粒度执行轮询或故障切换
- 协议转换：OpenAI Chat 可转发到 Anthropic Messages 或 OpenAI Responses
- 请求日志：记录协议、模型、延迟、Token、成本
- 配置备份：导出/导入站点、渠道、模型组、价格

## 快速开始

### Docker Compose（推荐）

```bash
mkdir lens && cd lens
curl -fsSLO https://raw.githubusercontent.com/dyedd/lens/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/dyedd/lens/main/.env.example
cp .env.example .env
```

编辑 `.env`，根据需要修改配置项。必须设置 `LENS_AUTH_SECRET_KEY`。

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

访问 `http://127.0.0.1:3000`，默认账号 `admin/admin`。首次登录后请立即修改默认管理员密码。

### Docker Run

```bash
mkdir -p data

docker run -d --name lens \
  --env-file .env \
  -p 3000:3000 \
  -v "$(pwd)/data:/app/data" \
  ghcr.io/dyedd/lens:latest
```

### 本地构建镜像

```bash
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

也可以手动构建后直接运行：

```bash
docker build -t lens:local .

mkdir -p data

docker run -d --name lens \
  --env-file .env \
  -p 3000:3000 \
  -v "$(pwd)/data:/app/data" \
  lens:local
```

### 本地开发

```bash
pip install -e ".[dev]"
cd ui && pnpm install && cd ..
lens db upgrade
lens seed-admin --username admin --password admin
lens dev
```

本地开发默认端口：
- Next.js dev server：`http://127.0.0.1:3000`
- FastAPI 后端：`http://127.0.0.1:18080`

也可以分开启动：

```bash
lens serve

cd ui
pnpm dev
```

## 使用流程

### 1. 添加上游站点

进入 `/channels`，新建站点，填写 Base URL 和 API Key，发现或手动添加模型。

常见 Base URL：

| 上游类型            | Base URL 示例                         | 协议选择         |
| ------------------- | ------------------------------------- | ---------------- |
| OpenAI              | `https://api.openai.com`              | OpenAI Chat / Responses / Embeddings |
| Anthropic           | `https://api.anthropic.com`           | Anthropic        |
| Gemini              | `https://generativelanguage.googleapis.com` | Gemini |
| NewAPI / Rerank     | `https://newapi.example.com`          | Rerank（透传到 `POST /v1/rerank`） |

### 2. 创建模型组

进入 `/groups`，新建模型组，选择协议，添加上游模型，选择路由策略：

- **轮询**：在模型组成员展开后的 key 级候选之间平滑轮询
- **故障切换**：优先使用前面的成员，失败后切到下一个 key 或渠道

**协议转换**：当前支持把 OpenAI Chat 上游加入 Anthropic 或 OpenAI Responses 模型组，运行时会自动转换。

### 3. 发放网关 Key

进入 `/api-keys`，新建 Key，复制 `sk-lens-...` 给客户端。

### 4. 客户端调用

客户端只需要：Lens Base URL + 网关 API Key + 模型组名称。

## 技术栈

| 层     | 技术                                                           |
| ------ | -------------------------------------------------------------- |
| 后端   | Python 3.11+、FastAPI、SQLAlchemy、Alembic、SQLite / PostgreSQL |
| 前端   | Next.js 16、React 19、TypeScript、TanStack Query、shadcn/ui    |

## 环境变量

核心变量：

| 变量                             | 默认值                                | 说明                                            |
| -------------------------------- | ------------------------------------- | ----------------------------------------------- |
| `LENS_HOST`                      | `127.0.0.1`                           | 后端监听地址；Docker 中设为 `0.0.0.0`           |
| `LENS_PORT`                      | `18080`                               | 后端监听端口；Docker 中设为 `3000`              |
| `LENS_DATABASE_URL`              | `sqlite+aiosqlite:///./data/data.db`  | 数据库连接；默认 SQLite，也可指向外部 PostgreSQL |
| `LENS_AUTH_SECRET_KEY`           | 必填                                  | JWT 签名密钥                                 |
| `LENS_REQUEST_TIMEOUT_SECONDS`   | `180`                                 | 上游请求超时                                     |

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
lens db upgrade                               # 升级到最新
lens db downgrade                             # 回退一步
lens db revision -m "describe your change"    # 生成新迁移
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
