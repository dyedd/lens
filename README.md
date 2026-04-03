# Lens

Lens 是一个基于 Python + Next.js 的模型网关与管理后台，当前只聚焦 4 类原生协议：

- OpenAI Chat Completions
- OpenAI Responses
- Anthropic Messages
- Gemini `generateContent` / `streamGenerateContent`

当前范围刻意保持收敛：

- 不做协议互转
- 使用 SQLite + SQLAlchemy ORM
- 使用 Alembic 做显式数据库迁移
- 提供管理员登录
- 提供渠道管理
- 提供模型组聚合
- 网关 API Key 在设置页管理
- 提供请求日志与总览统计

## 当前形态

管理后台页面：

- `/login`
- `/dashboard`
- `/dashboard/requests`
- `/dashboard/channels`
- `/dashboard/groups`
- `/dashboard/settings`

网关接口：

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/messages`
- `POST /v1beta/models/{model}:generateContent`
- `POST /v1beta/models/{model}:streamGenerateContent`

管理 API：

- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/overview`
- `GET /api/request-logs`
- `GET /api/sites`
- `POST /api/sites`
- `PUT /api/sites/{site_id}`
- `DELETE /api/sites/{site_id}`
- `GET /api/router`
- `POST /api/router/preview`
- `GET /api/model-groups`
- `GET /api/model-groups/stats`
- `POST /api/model-groups`
- `PUT /api/model-groups/{group_id}`
- `DELETE /api/model-groups/{group_id}`
- `GET /api/settings`
- `PUT /api/settings`

## 技术栈

- 后端：FastAPI、HTTPX、SQLAlchemy 2.x、SQLite、Alembic
- 前端：Next.js App Router、React 19、TypeScript、TanStack Query、pnpm

## 运行后端

使用 `temp` conda 环境。

```powershell
conda activate temp
cd D:\Projects\PYprojects\lens
python -m pip install -e .[dev]
alembic upgrade head
python scripts/seed_admin.py
python -m lens.main
```

如果 `data/data.db` 已经存在，但不是由当前 Alembic 迁移流程创建的，请先删除后再执行 `alembic upgrade head`。

默认后端地址：

- `http://127.0.0.1:18080`

## 运行前端

```powershell
conda activate temp
cd D:\Projects\PYprojects\lens\ui
pnpm install
pnpm dev
```

默认前端地址：

- `http://127.0.0.1:3000`

## 默认管理员

执行 `python scripts/seed_admin.py` 后会写入默认管理员：

- username: `admin`
- password: `admin`

在任何非本地场景中使用前，请修改 `LENS_AUTH_SECRET_KEY` 和默认管理员密码。

## 环境变量

后端支持的配置项：

```env
LENS_HOST=127.0.0.1
LENS_PORT=18080
LENS_DATABASE_URL=sqlite+aiosqlite:///data/data.db
LENS_AUTH_SECRET_KEY=change-me-in-production-and-make-it-longer-than-32-bytes
LENS_AUTH_ALGORITHM=HS256
LENS_AUTH_ACCESS_TOKEN_MINUTES=720
LENS_ADMIN_DEFAULT_USERNAME=admin
LENS_ADMIN_DEFAULT_PASSWORD=admin
LENS_ANTHROPIC_VERSION=2023-06-01
LENS_REQUEST_TIMEOUT_SECONDS=180
LENS_CONNECT_TIMEOUT_SECONDS=10
LENS_MAX_CONNECTIONS=200
LENS_MAX_KEEPALIVE_CONNECTIONS=50
```

## 路由规则

Lens 只会在同一种原生协议族内做路由。

路由流程：

1. Authenticate the incoming gateway API key.
2. Read requested protocol and model.
3. If the model exactly matches a model-group name under the same protocol, use that group strategy and channel pool.
4. Otherwise fall back to channel-level model matching.
5. Route with `round_robin` or `failover`.

渠道级聚合通过后台中手工选择的模型列表配置。

示例：

```text
^claude-opus-4-6$
^claude-opus-.*$
```

如果你创建一个名为 `claude-opus-4-6` 的模型组，那么这个外部模型名可以直接映射到指定的内部渠道池。

## 下游网关访问

先在 `/dashboard?view=settings` 中创建一个或多个网关 API Key，然后通过以下任一方式调用 Lens：

- `Authorization: Bearer <gateway-secret>`
- `x-api-key: <gateway-secret>`
- `x-goog-api-key: <gateway-secret>`

OpenAI Chat 调用示例：

```bash
curl http://127.0.0.1:18080/v1/chat/completions \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hello"}]}'
```

## 已实现

- 管理员认证
- SQLite 持久化，基于 SQLAlchemy ORM + Alembic
- 渠道、模型组、设置的 CRUD
- 基于模型组和渠道模型选择的路由
- OpenAI Chat、OpenAI Responses、Anthropic、Gemini 原生透传
- `/v1/*` 网关 API Key 鉴权
- 管理后台中的请求日志与总览统计

## 尚未实现

- 协议互转
- 主动健康检查和熔断逻辑
- 上游模型自动同步
- 完整成本核算
- 多管理员 RBAC
