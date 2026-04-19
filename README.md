# Lens

多供应商 LLM 网关与管理后台，原生支持以下客户端协议与上游协议：

- OpenAI Chat Completions / Responses
- Anthropic Messages
- Gemini generateContent / streamGenerateContent

默认按协议直连上游。当前已支持的协议互转场景为：

- 上游渠道协议为 `OpenAI Chat`，对外客户端协议为 `Anthropic Messages`
- 上游渠道协议为 `OpenAI Chat`，对外客户端协议为 `OpenAI Responses`

也就是客户端可以分别通过 `/v1/messages` 或 `/v1/responses` 接入，Lens 会先将请求转换为 `OpenAI Chat` 发往上游，再将上游响应转换回客户端所使用的协议。

## 技术栈

- 后端：Python 3.11+、FastAPI、SQLAlchemy 2.x、Alembic、SQLite
- 前端：Next.js (App Router)、React 19、TypeScript、TanStack Query
- 包管理：pip (后端)、pnpm (前端)

## 快速开始

### 后端

```bash
pip install -e .[dev]
lens db upgrade
lens seed-admin --username admin --password admin

# 开发模式（支持热重载）
lens serve --reload
```

后端默认监听 `http://127.0.0.1:18080`。

生产环境使用 `lens serve`（不带 `--reload`）。

### 前端

```bash
cd ui
pnpm install
pnpm dev
```

前端默认监听 `http://127.0.0.1:3000`，开发模式下自动代理 API 请求到后端。

代理目标可通过环境变量覆盖：

```env
LENS_UI_BACKEND_BASE_URL=http://127.0.0.1:18080
```

管理后台登录页是 `http://127.0.0.1:3000/login`，登录后主要页面为：

- `/`
- `/requests`
- `/channels`
- `/groups`
- `/settings`

## Docker

### 本地构建并启动

先复制环境变量文件：

```bash
cp .env.example .env
```

然后启动应用容器：

```bash
docker compose up --build
```

首次启动后，如需初始化管理员账号：

```bash
docker compose exec app python -m lens_api.cli seed-admin --username admin --password admin
```

说明：

- 单个容器会同时运行后端 API 和前端 Next 服务
- 容器启动时会自动执行 `lens db upgrade`
- 宿主机 `./data` 会挂载到容器内 `/app/data`，SQLite 数据会持久化保留
- 前端默认通过 `LENS_UI_BACKEND_BASE_URL=http://127.0.0.1:18080` 访问同容器内的后端服务；这个值在 Docker 中属于前端构建参数，如需覆盖，需要在根目录 `.env` 中修改后重新执行 `docker compose up --build`
- 如需跳过启动时自动迁移，可为后端设置 `LENS_SKIP_DB_UPGRADE=1`
- `http://127.0.0.1:3000` 提供管理后台，`http://127.0.0.1:18080` 仍可直接访问后端和网关接口

### 直接拉取镜像

直接拉取默认镜像：

```bash
docker pull ghcr.io/dyedd/lens:latest
```

启动示例：

```bash
docker run --name lens \
  -p 3000:3000 \
  -p 18080:18080 \
  --env-file .env \
  -v ./data:/app/data \
  ghcr.io/dyedd/lens:latest
```

如果需要固定版本，可以把 `latest` 替换为具体 tag，例如：

```bash
docker pull ghcr.io/dyedd/lens:v1.2.3
docker pull ghcr.io/dyedd/lens:sha-<commit>
```

### 自定义镜像

如果你需要修改前端代理目标或打自己的镜像标签，可以直接本地构建：

```bash
docker build \
  -t your-registry/lens:custom \
  --build-arg LENS_UI_BACKEND_BASE_URL=http://127.0.0.1:18080 \
  .
```

然后像普通镜像一样运行：

```bash
docker run --name lens \
  -p 3000:3000 \
  -p 18080:18080 \
  --env-file .env \
  -v ./data:/app/data \
  your-registry/lens:custom
```

## 数据库迁移

通过 `lens db` 命令或 `alembic` 命令管理 Alembic 迁移。仓库根目录现在包含正式的 [alembic.ini](./alembic.ini)。

```bash
lens db upgrade                               # 升级到最新
lens db downgrade                             # 回退一步
lens db revision -m "describe your change"    # 生成新迁移（自动检测模型变更）
lens db current                               # 查看当前版本
lens db history                               # 查看迁移历史
lens db stamp head                            # 标记数据库为最新（不执行 SQL）
```

## 环境变量

所有配置项通过 `LENS_` 前缀的环境变量设置，也支持 `.env` 文件。

常用部署项：

| 变量                       | 默认值                             | 说明                                                                               |
| -------------------------- | ---------------------------------- | ---------------------------------------------------------------------------------- |
| `LENS_DATABASE_URL`        | `sqlite+aiosqlite:///data/data.db` | 数据库连接                                                                         |
| `LENS_AUTH_SECRET_KEY`     | `lens-dev-jwt-signing-secret-2026-default` | 后台 JWT 签名密钥，生产环境必须修改                                                |
| `LENS_UI_BACKEND_BASE_URL` | `http://127.0.0.1:18080`           | 前端代理到后端的目标地址；本地 `pnpm dev` 直接读取，自定义 Docker 镜像时也可通过 build arg 覆盖 |

其余配置项如果未显式设置，会使用内置默认值：

- `LENS_HOST=127.0.0.1`
- `LENS_PORT=18080`
- `LENS_AUTH_ALGORITHM=HS256`
- `LENS_AUTH_ACCESS_TOKEN_MINUTES=720`
- `LENS_REQUEST_TIMEOUT_SECONDS=180`
- `LENS_CONNECT_TIMEOUT_SECONDS=10`
- `LENS_MAX_CONNECTIONS=200`
- `LENS_MAX_KEEPALIVE_CONNECTIONS=50`
- `LENS_ANTHROPIC_VERSION=2023-06-01`

## 网关使用

在管理后台设置页创建网关 API Key 后，通过以下任一方式鉴权：

```
Authorization: Bearer <key>
x-api-key: <key>
x-goog-api-key: <key>
```

调用示例：

```bash
curl http://127.0.0.1:18080/v1/chat/completions \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hello"}]}'
```

```bash
curl http://127.0.0.1:18080/v1/messages \
  -H "x-api-key: sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"my-anthropic-group","max_tokens":256,"messages":[{"role":"user","content":"hello"}]}'
```

```bash
curl http://127.0.0.1:18080/v1/responses \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"my-responses-group","input":"hello"}'
```

其中 `/v1/messages` 和 `/v1/responses` 若要走到 `openai_chat` 上游，需要先在管理后台创建对应客户端协议的模型组，并将 `openai_chat` 渠道挂到组内。

## 路由规则

请求处理流程：

1. 验证网关 API Key
2. 识别协议和请求模型
3. 若模型名精确匹配某个模型组，优先使用该组的策略和渠道池
4. 若模型组内存在可承载当前客户端协议的渠道，则该组可按配置执行协议转换；当前仅支持以下两种“上游 OpenAI Chat，对外客户端协议不同”的场景：
   - 上游渠道协议 `OpenAI Chat`，对外客户端协议 `Anthropic Messages`
   - 上游渠道协议 `OpenAI Chat`，对外客户端协议 `OpenAI Responses`
5. 若未命中模型组，则回退到渠道级模型匹配；这条路径仅做同协议匹配，不会自动跨协议选择渠道
6. 按 `round_robin` 或 `failover` 策略分发

模型组示例：创建一个协议为 `anthropic` 的模型组并挂载 `openai_chat` 渠道，外部客户端通过 `/v1/messages` 请求该组名时，会先转成 `OpenAI Chat` 请求发往上游，再将响应转回 `Anthropic Messages` 格式。
