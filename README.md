<p align="center">
  <img src="./ui/public/logo.svg" alt="Lens" width="88" height="88">
</p>

<h1 align="center">Lens</h1>

<p align="center">
  自托管的多供应商 LLM 网关与管理后台，把分散的模型服务统一成一个入口、一套网关 API Key 和一组可管理的模型名称。
</p>

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

Lens 是一个自托管的多供应商 LLM 网关与管理后台。它把分散的上游模型服务统一成一个入口、一套网关 API Key 和一组可管理的模型名称，适合个人、团队或内部工具统一接入 OpenAI、Anthropic、Gemini 以及 OpenAI 兼容服务。

## 适合解决的问题

- 下游工具里不想反复配置多个供应商、多个 Base URL、多个 API Key
- 同一个模型名希望挂载多个上游渠道，按策略轮询或故障切换
- 希望用 OpenAI、Anthropic、Gemini 风格的客户端访问同一套网关
- 需要查看请求日志、Token 用量、延迟、成功率和成本估算
- 需要把渠道、模型组、价格、系统设置等配置导出备份或导入迁移

## 核心功能

### 多协议统一入口

Lens 对外提供常见 LLM API 路径：

| 客户端协议                   | 路径                                           |
| ---------------------------- | ---------------------------------------------- |
| OpenAI Chat Completions      | `/v1/chat/completions`                         |
| OpenAI Responses             | `/v1/responses`                                |
| Anthropic Messages           | `/v1/messages`                                 |
| OpenAI Models                | `/v1/models`                                   |
| Gemini generateContent       | `/v1beta/models/{model}:generateContent`       |
| Gemini streamGenerateContent | `/v1beta/models/{model}:streamGenerateContent` |

鉴权支持：

```http
Authorization: Bearer <gateway-key>
x-api-key: <gateway-key>
x-goog-api-key: <gateway-key>
```

### 上游站点与渠道管理

- 一个站点可配置多个 Base URL、多个凭证、多个协议和模型列表
- 支持按协议管理 OpenAI Chat、OpenAI Responses、Anthropic、Gemini 渠道
- 支持从上游发现模型，减少手动录入
- 支持全局代理、CORS、站点名称和 Logo 等运行时配置

### 模型组与路由

- 模型组是对外暴露的模型名，例如把多个上游的 `gpt-4o-mini` 聚合成一个统一名称
- 当前路由策略：
  - `round_robin`：按平滑轮询分发请求
  - `failover`：优先使用前序渠道，失败后切换
- 支持健康窗口、失败惩罚、断路器冷却，降低异常渠道被持续命中的概率
- 支持路由预览和运行时路由快照，便于排查请求会走到哪个上游

### 协议转换

同协议会直连转发。当前已支持的跨协议转换：

| 上游渠道协议 | 对外客户端协议     | 说明                                                                       |
| ------------ | ------------------ | -------------------------------------------------------------------------- |
| OpenAI Chat  | Anthropic Messages | `/v1/messages` 请求转换为 Chat Completions，上游响应再转回 Anthropic 格式  |
| OpenAI Chat  | OpenAI Responses   | `/v1/responses` 请求转换为 Chat Completions，上游响应再转回 Responses 格式 |

### 可观测性与成本

- 请求日志：协议、模型、状态、延迟、Token 用量、错误上下文、尝试链路
- 仪表盘：请求量、成功率、平均延迟、Token 趋势、模型维度统计
- 模型价格：支持从 `models.dev` 同步价格，也可以在管理后台手动维护价格
- 统计数据按配置周期落库，避免每次请求都产生高频写入

### 管理后台

后台页面：

- `/`：概览
- `/channels`：站点、渠道、凭证、模型管理
- `/groups`：模型组、路由策略、价格维护
- `/requests`：请求日志和详情
- `/settings`：网关 API Key、系统设置、配置导入导出、账号设置

## 技术栈

| 层     | 技术                                                           |
| ------ | -------------------------------------------------------------- |
| 后端   | Python 3.11+、FastAPI、SQLAlchemy 2.x、Alembic、SQLite         |
| 前端   | Next.js 16、React 19、TypeScript、TanStack Query、shadcn/ui    |
| 容器   | 多阶段构建，Node 仅用于前端构建，最终镜像为 `python:3.14-slim` |
| 包管理 | pip、pnpm                                                      |

## 快速开始

### Docker Compose

复制环境变量示例：

```bash
cp .env.example .env
```

启动：

```bash
docker compose up --build
```

访问：

- 管理后台与网关：`http://127.0.0.1:3000`
- 健康检查：`http://127.0.0.1:3000/healthz`

默认管理员：

```text
username: admin
password: admin
```

首次登录后请立即修改默认管理员密码，并在生产环境中修改 `LENS_AUTH_SECRET_KEY`。

Docker 说明：

- 单容器同时提供静态前端和 FastAPI 网关
- 容器启动时自动执行 `lens db upgrade`
- 容器启动时会尝试初始化默认管理员；如果已存在管理员则跳过
- `./data` 挂载到容器内 `/app/data`，SQLite 数据会持久化
- 如需跳过启动时迁移，可设置 `LENS_SKIP_DB_UPGRADE=1`

### Docker Run

```bash
docker run -d --name lens \
  -p 3000:3000 \
  --env-file .env \
  -v ./data:/app/data \
  ghcr.io/dyedd/lens:latest
```

如果使用本地构建镜像：

```bash
docker build -t lens:local .

docker run -d --name lens \
  -p 3000:3000 \
  --env-file .env \
  -v ./data:/app/data \
  lens:local
```

### 本地开发

安装后端：

```bash
pip install -e .[dev]
```

安装前端依赖：

```bash
cd ui
pnpm install
cd ..
```

初始化数据库和管理员：

```bash
lens db upgrade
lens seed-admin --username admin --password admin
```

一键启动开发环境：

```bash
lens dev
```

本地开发端口：

- Next.js dev server：`http://127.0.0.1:3000`
- FastAPI 后端：`http://127.0.0.1:18080`
- `lens dev` 会让前端自动代理 API 请求到后端，并保留前端 HMR 与后端 reload

也可以分开启动：

```bash
lens serve --reload

cd ui
pnpm dev
```

## 客户端接入

先在管理后台的设置页创建网关 API Key，然后将下游客户端的 Base URL 指向 Lens。

### OpenAI SDK

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

### Anthropic Messages

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

### OpenAI Responses

```bash
curl http://127.0.0.1:3000/v1/responses \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-responses-group",
    "input": "hello"
  }'
```

### Gemini

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

### Claude Code

示例环境变量：

```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:3000
ANTHROPIC_AUTH_TOKEN=sk-lens-...
ANTHROPIC_MODEL=your-anthropic-group
ANTHROPIC_SMALL_FAST_MODEL=your-anthropic-group
```

### Codex

示例 `~/.codex/config.toml`：

```toml
model = "your-model-group"
model_provider = "lens"

[model_providers.lens]
name = "Lens"
base_url = "http://127.0.0.1:3000/v1"
```

示例 `~/.codex/auth.json`：

```json
{
  "OPENAI_API_KEY": "sk-lens-..."
}
```

## 路由规则

请求处理流程：

1. 验证网关 API Key
2. 根据请求路径识别客户端协议
3. 从请求体中读取模型名
4. 如果模型名精确匹配模型组，优先使用模型组内的渠道池和策略
5. 如果模型组内渠道协议与客户端协议不同，则仅在支持的转换场景中执行协议转换
6. 如果没有命中模型组，则回退到渠道级模型匹配；这条路径只做同协议匹配
7. 根据 `round_robin` 或 `failover` 策略选择上游
8. 记录请求日志、Token、成本、延迟和尝试结果

## 数据库迁移

```bash
lens db upgrade                               # 升级到最新
lens db downgrade                             # 回退一步
lens db revision -m "describe your change"    # 生成新迁移
lens db current                               # 查看当前版本
lens db history                               # 查看迁移历史
lens db stamp head                            # 标记数据库为最新
```

## 环境变量

后端配置项使用 `LENS_` 前缀，也支持 `.env` 文件；本地前端开发会额外读取 `LENS_UI_BACKEND_BASE_URL` 作为代理目标。

| 变量                             | 默认值                             | 说明                                  |
| -------------------------------- | ---------------------------------- | ------------------------------------- |
| `LENS_HOST`                      | `127.0.0.1`                        | 后端监听地址；Docker 中设为 `0.0.0.0` |
| `LENS_PORT`                      | `18080`                            | 后端监听端口；Docker 中设为 `3000`    |
| `LENS_DATABASE_URL`              | `sqlite+aiosqlite:///data/data.db` | 数据库连接                            |
| `LENS_AUTH_SECRET_KEY`           | 开发默认值                         | JWT 签名密钥，生产环境必须修改        |
| `LENS_AUTH_ACCESS_TOKEN_MINUTES` | `720`                              | 管理后台登录有效期                    |
| `LENS_REQUEST_TIMEOUT_SECONDS`   | `180`                              | 上游请求总超时                        |
| `LENS_CONNECT_TIMEOUT_SECONDS`   | `10`                               | 上游连接超时                          |
| `LENS_MAX_CONNECTIONS`           | `200`                              | HTTP 连接池最大连接数                 |
| `LENS_MAX_KEEPALIVE_CONNECTIONS` | `50`                               | HTTP 连接池 keep-alive 数             |
| `LENS_ANTHROPIC_VERSION`         | `2023-06-01`                       | 转发 Anthropic 请求时使用的版本头     |
| `LENS_UI_STATIC_DIR`             | 空                                 | 静态前端目录；Docker 内部使用         |
| `LENS_UI_BACKEND_BASE_URL`       | `http://127.0.0.1:18080`           | 仅用于本地 Next.js dev 代理           |
| `LENS_SKIP_DB_UPGRADE`           | `0`                                | Docker 启动时设为 `1` 可跳过自动迁移  |

更多运行时设置，例如 CORS、代理、日志保留、断路器、健康评分、站点名称和 Logo，可在管理后台设置页调整。

## 配置备份与迁移

管理后台支持导出和导入配置包，覆盖：

- 站点、Base URL、凭证、协议绑定、模型列表
- 模型组与路由策略
- 网关 API Key
- 模型价格
- 系统设置
- 可选统计快照和请求日志

导入前建议先备份当前数据目录。

## 安全建议

- 生产环境必须修改 `LENS_AUTH_SECRET_KEY`
- 首次登录后立即修改默认管理员用户名或密码
- 为不同客户端创建独立网关 API Key，便于禁用和审计
- 不要把 `.env`、`data/` 或数据库文件提交到仓库
- 如暴露到公网，建议放在 HTTPS 反向代理之后
