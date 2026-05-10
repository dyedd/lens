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
| OpenAI Embeddings            | `/v1/embeddings`                               |
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
- 统计数据通过定时任务落库，避免每次请求都产生高频聚合写入

### 管理后台

后台页面：

- `/`：概览
- `/channels`：站点、渠道、凭证、模型管理
- `/groups`：模型组、路由策略、价格维护
- `/requests`：请求日志和详情
- `/api-keys`：网关 API Key 管理
- `/cronjobs`：定时任务、日志清理计划
- `/backups`：配置导出和导入恢复
- `/settings`：系统设置、站点信息、账号设置

## 技术栈

| 层     | 技术                                                           |
| ------ | -------------------------------------------------------------- |
| 后端   | Python 3.11+、FastAPI、SQLAlchemy 2.x、Alembic、SQLite         |
| 前端   | Next.js 16、React 19、TypeScript、TanStack Query、shadcn/ui    |
| 容器   | 多阶段构建，Node 仅用于前端构建，最终镜像为 `python:3.14-slim` |
| 包管理 | pip、pnpm                                                      |

## 快速开始

### Docker Compose

在部署目录中放置 `docker-compose.yml`，并新建 `.env`：

```bash
mkdir lens
cd lens
curl -fsSLO https://raw.githubusercontent.com/dyedd/lens/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/dyedd/lens/main/.env.example
cp .env.example .env
```

启动前请编辑 `.env`，至少修改 `LENS_AUTH_SECRET_KEY`。

如需修改数据目录，只改 `volumes` 左侧的宿主机路径，右侧 `/app/data` 保持不变：

```yaml
volumes:
  - ./data:/app/data
```

拉取并启动线上镜像：

```bash
docker compose pull
docker compose up -d
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
- 容器内部固定监听 `0.0.0.0:3000`；不要用 `PORT` 或 `HOSTNAME` 配置 Lens
- 如需跳过启动时迁移，可设置 `LENS_SKIP_DB_UPGRADE=1`

### Docker Run

```bash
mkdir -p data

docker run -d --name lens \
  --env-file .env \
  -p 3000:3000 \
  -v "$(pwd)/data:/app/data" \
  ghcr.io/dyedd/lens:latest
```

`docker run` 示例假设当前目录已经有从 `.env.example` 复制并修改过的 `.env`。不要在这个 `.env` 里把 `LENS_PORT` 设成本地开发端口，容器内应保持 `LENS_HOST=0.0.0.0`、`LENS_PORT=3000`。

如果使用本地构建镜像：

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

`docker-compose.local.yml` 需要和 `docker-compose.yml` 放在同一目录；仓库中已提供该文件，会把镜像名改成 `lens:local`，并从当前源码构建。

如果你是在独立部署目录中本地构建，手动新建 `docker-compose.local.yml`：

```yaml
services:
  app:
    image: lens:local
    build:
      context: .
      dockerfile: Dockerfile
```

然后把项目源码放在同一目录，执行：

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

也可以手动构建后不用 Compose，直接运行：

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

安装后端：

```bash
pip install -e ".[dev]"
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

本地开发默认端口：

- Next.js dev server：`http://127.0.0.1:3000`，如果端口被占用，以 Next.js 输出为准
- FastAPI 后端：`http://127.0.0.1:18080`
- `lens dev` 会让前端自动代理 API 请求到后端，并保留前端 HMR 与后端 reload

也可以分开启动：

```bash
lens serve --reload

cd ui
pnpm dev
```

## 首次使用流程

完成部署并登录管理后台后，按下面顺序配置。Lens 的核心链路是：先配置上游渠道，再把上游模型加入模型组，最后给客户端发放网关 API Key。

### 1. 修改管理员账号

进入 `/settings`：

- 修改默认管理员密码
- 按需设置站点名称、Logo、业务时区、CORS 和全局代理
- 业务时区默认是 `Asia/Shanghai`，会影响请求日志时间、统计分桶、今天窗口、定时任务执行时间和备份文件名

### 2. 添加上游站点和渠道

进入 `/channels`，新建一个站点：

1. 填写站点名称，例如 `OpenAI`、`Anthropic`、`Gemini` 或内部兼容服务名称
2. 添加 Base URL，例如 `https://api.openai.com`
3. 添加上游 API Key
4. 添加协议配置，选择上游真实支持的协议，例如 `OpenAI Chat`
5. 点击发现模型，或手动录入模型名
6. 保留需要使用的模型为启用状态

常见 Base URL 示例：

| 上游类型            | Base URL 示例                         | 协议选择         |
| ------------------- | ------------------------------------- | ---------------- |
| OpenAI              | `https://api.openai.com`              | OpenAI Chat      |
| OpenAI 兼容服务     | `https://example.com`                 | OpenAI Chat      |
| Anthropic           | `https://api.anthropic.com`           | Anthropic        |
| Gemini              | `https://generativelanguage.googleapis.com` | Gemini |

上游 Base URL 推荐填写服务根地址。Lens 会按协议自动补 `/v1` 或 `/v1beta`，也会兼容已经带 `/v1`、`/v1beta` 的地址。

### 3. 创建模型组

进入 `/groups`，新建模型组。模型组名称就是客户端请求时使用的 `model`。

例如希望客户端使用 `gpt-4o-mini`：

1. 模型组名称填 `gpt-4o-mini`
2. 协议选择客户端要调用的协议，例如 `OpenAI Chat`
3. 从候选列表加入一个或多个上游模型
4. 选择路由策略：
   - `round_robin`：多个成员按平滑轮询分发
   - `failover`：优先使用前面的成员，失败后切到后面的成员
5. 保存后可用路由预览确认请求会命中哪些上游

模型组协议代表“客户端入口协议”，不要求所有成员都和它完全同协议。当前支持把 OpenAI Chat 上游加入 Anthropic 或 OpenAI Responses 模型组，运行时会自动转换请求和响应。

示例：

| 客户端入口协议     | 模型组名称       | 可加入的上游成员                         |
| ------------------ | ---------------- | ---------------------------------------- |
| OpenAI Chat        | `gpt-4o-mini`    | OpenAI Chat 上游模型                     |
| Anthropic Messages | `claude-alias`   | Anthropic 上游模型，或 OpenAI Chat 上游模型 |
| OpenAI Responses   | `responses-main` | OpenAI Responses 上游模型，或 OpenAI Chat 上游模型 |
| Gemini             | `gemini-main`    | Gemini 上游模型                          |

### 4. 维护模型价格

进入 `/groups` 的价格区域：

- 可以从 `models.dev` 同步价格
- 也可以手动维护模型组的输入、输出、缓存价格
- 请求日志和仪表盘的成本估算会使用这里的价格

### 5. 创建网关 API Key

进入 `/api-keys`：

1. 新建一个网关 API Key
2. 按需限制可用模型组、最大消费金额和过期时间
3. 把生成的 `sk-lens-...` 发给下游客户端

下游客户端只需要知道：

- Lens Base URL
- 网关 API Key
- 模型组名称

### 6. 调用并排查

客户端调用后：

- 在 `/requests` 查看请求状态、协议、模型组、上游模型、延迟、Token、成本和错误详情
- 在 `/` 查看整体请求量、成功率、延迟和模型趋势
- 在 `/cronjobs` 配置日志清理、统计落库、模型价格同步等定时任务
- 在 `/backups` 导出配置包，迁移或升级前建议先备份

## 客户端接入

先完成“首次使用流程”，确保已有模型组和网关 API Key，然后将下游客户端的 Base URL 指向 Lens。

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

| 变量                             | 默认值                                | 说明                                            |
| -------------------------------- | ------------------------------------- | ----------------------------------------------- |
| `LENS_HOST`                      | `127.0.0.1`                           | 后端监听地址；Docker 中设为 `0.0.0.0`           |
| `LENS_PORT`                      | `18080`                               | 后端监听端口；Docker 中设为 `3000`              |
| `LENS_DATABASE_URL`              | `sqlite+aiosqlite:///./data/data.db`  | 数据库连接；默认写入当前工作目录下的 `data`     |
| `LENS_AUTH_SECRET_KEY`           | 开发默认值                            | JWT 签名密钥，生产环境必须修改                  |
| `LENS_AUTH_ACCESS_TOKEN_MINUTES` | `720`                                 | 管理后台登录有效期                              |
| `LENS_REQUEST_TIMEOUT_SECONDS`   | `180`                                 | 上游请求总超时                                  |
| `LENS_CONNECT_TIMEOUT_SECONDS`   | `10`                                  | 上游连接超时                                    |
| `LENS_MAX_CONNECTIONS`           | `200`                                 | HTTP 连接池最大连接数                           |
| `LENS_MAX_KEEPALIVE_CONNECTIONS` | `50`                                  | HTTP 连接池 keep-alive 数                       |
| `LENS_ANTHROPIC_VERSION`         | `2023-06-01`                          | 转发 Anthropic 请求时使用的版本头               |
| `LENS_UI_STATIC_DIR`             | 空                                    | 静态前端目录；Docker 内部设为 `/app/ui`         |
| `LENS_SKIP_DB_UPGRADE`           | `0`                                   | Docker 启动时设为 `1` 可跳过自动迁移            |
| `LENS_UI_BACKEND_BASE_URL`       | `http://127.0.0.1:18080`              | 仅用于本地 Next.js dev/standalone 代理          |

监听地址和端口由 `LENS_HOST` 和 `LENS_PORT` 控制；通用的 `HOSTNAME`、`PORT` 不会影响后端监听地址和端口。

Docker 镜像和 `docker-compose.yml` 会把数据库连接显式设为 `sqlite+aiosqlite:////app/data/data.db`，本地开发默认使用 `sqlite+aiosqlite:///./data/data.db`；部署目录的 `.env` 不需要再写 `LENS_DATABASE_URL`，避免覆盖容器内路径。

Lens 的业务时区不是环境变量；在 `/settings` 选择，默认 `Asia/Shanghai`。请求日志时间、今天窗口、趋势分桶、备份文件名等应用内时间显示都会使用这个设置。

更多运行时设置，例如 CORS、代理、断路器、健康评分、站点名称和 Logo，可在 `/settings` 调整；日志保留和清理计划在 `/cronjobs` 调整。

## 配置备份与迁移

管理后台支持导出和导入配置包，覆盖：

- 站点、Base URL、凭证、协议绑定、模型列表
- 模型组与路由策略
- 网关 API Key
- 模型价格
- 系统设置
- 定时任务
- 可选统计快照和请求日志

导入前建议先备份当前数据目录。

## 安全建议

- 生产环境必须修改 `LENS_AUTH_SECRET_KEY`
- 首次登录后立即修改默认管理员用户名或密码
- 为不同客户端创建独立网关 API Key，便于禁用和审计
- 不要把 `.env`、`data/` 或数据库文件提交到仓库
- 如暴露到公网，建议放在 HTTPS 反向代理之后

## 致谢

Lens 从以下项目获得灵感，并受益于社区交流：

- [bestruirui/octopus](https://github.com/bestruirui/octopus)
- [cita-777/metapi](https://github.com/cita-777/metapi)
- [caidaoli/ccLoad](https://github.com/caidaoli/ccLoad)
- [Linux DO 社区](https://linux.do/)
