# Lens

多供应商 LLM 网关与管理后台，原生透传以下协议：

- OpenAI Chat Completions / Responses
- Anthropic Messages
- Gemini generateContent / streamGenerateContent

不做协议互转，只在同协议族内路由和聚合。

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

## Docker Compose

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
| `LENS_UI_BACKEND_BASE_URL` | `http://127.0.0.1:18080`           | 前端代理到后端的目标地址；本地 `pnpm dev` 直接读取，Docker 需要重新 build 才会生效 |

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

## 路由规则

Lens 只在同协议族内路由，流程：

1. 验证网关 API Key
2. 识别协议和请求模型
3. 若模型名精确匹配某个模型组，使用该组的策略和渠道池
4. 否则回退到渠道级模型匹配
5. 按 `round_robin` 或 `failover` 策略分发

模型组示例：创建名为 `claude-opus-4-6` 的模型组，外部请求该模型名时直接路由到组内配置的渠道池。
