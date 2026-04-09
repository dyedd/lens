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

- `POST /api/admin/session`
- `GET /api/admin/session`
- `PUT /api/admin/password`
- `GET /api/admin/app-info`
- `GET /api/admin/overview`
- `GET /api/admin/overview-summary`
- `GET /api/admin/overview-daily`
- `GET /api/admin/overview-models`
- `GET /api/admin/request-logs`
- `DELETE /api/admin/request-logs`
- `GET /api/admin/request-logs/{log_id}`
- `GET /api/admin/sites`
- `POST /api/admin/sites`
- `PUT /api/admin/sites/{site_id}`
- `DELETE /api/admin/sites/{site_id}`
- `POST /api/admin/site-model-discoveries`
- `GET /api/admin/routes`
- `POST /api/admin/route-previews`
- `GET /api/admin/model-groups`
- `GET /api/admin/model-group-stats`
- `POST /api/admin/model-group-candidates`
- `POST /api/admin/model-groups`
- `PUT /api/admin/model-groups/{group_id}`
- `DELETE /api/admin/model-groups/{group_id}`
- `GET /api/admin/model-prices`
- `PUT /api/admin/model-prices/{model_key}`
- `POST /api/admin/model-price-sync-jobs`
- `GET /api/admin/settings`
- `PUT /api/admin/settings`

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
python scripts/seed_admin.py --username admin --password admin
python -m lens_api.main
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

前端开发代理环境变量：

- `LENS_UI_BACKEND_BASE_URL=http://127.0.0.1:18080`

## 默认管理员

执行 `python scripts/seed_admin.py --username <name> --password <password>` 后会显式写入管理员。

本地开发示例：

```powershell
python scripts/seed_admin.py --username admin --password admin
```

应用启动不会再自动创建管理员，也不会自动导入统计文件、自动清理日志或自动同步价格。在任何非本地场景中使用前，请修改 `LENS_AUTH_SECRET_KEY`，并显式设置你自己的管理员密码。

## 环境变量

后端支持的配置项：

```env
LENS_HOST=127.0.0.1
LENS_PORT=18080
LENS_DATABASE_URL=sqlite+aiosqlite:///data/data.db
LENS_AUTH_SECRET_KEY=change-me-in-production-and-make-it-longer-than-32-bytes
LENS_AUTH_ALGORITHM=HS256
LENS_AUTH_ACCESS_TOKEN_MINUTES=720
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

如果前端使用 `pnpm dev` 跑在 `3000`，也可以直接把工具接到前端地址。Next.js 会把以下接口转发到后端 `LENS_UI_BACKEND_BASE_URL`：

- `/api/*`
- `/v1/chat/completions`
- `/v1/responses`
- `/v1/messages`
- `/v1/models`
- `/v1beta/*`

例如：

```bash
curl http://127.0.0.1:3000/v1/chat/completions \
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
