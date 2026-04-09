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
lens serve
```

后端默认监听 `http://127.0.0.1:18080`。

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

## 数据库迁移

通过 `lens db` 命令管理 Alembic 迁移，不需要 `alembic.ini`。

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

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LENS_HOST` | `127.0.0.1` | 监听地址 |
| `LENS_PORT` | `18080` | 监听端口 |
| `LENS_DATABASE_URL` | `sqlite+aiosqlite:///data/data.db` | 数据库连接 |
| `LENS_AUTH_SECRET_KEY` | (开发用默认值) | JWT 签名密钥，生产环境必须修改 |
| `LENS_AUTH_ACCESS_TOKEN_MINUTES` | `720` | Token 有效期（分钟） |
| `LENS_REQUEST_TIMEOUT_SECONDS` | `180` | 上游请求超时 |
| `LENS_CONNECT_TIMEOUT_SECONDS` | `10` | 上游连接超时 |
| `LENS_MAX_CONNECTIONS` | `200` | 连接池上限 |
| `LENS_MAX_KEEPALIVE_CONNECTIONS` | `50` | Keep-alive 连接上限 |

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
