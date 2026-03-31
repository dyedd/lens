# Lens

Lens is a Python + Next.js admin console and LLM gateway for four native protocol families:

- OpenAI Chat Completions
- OpenAI Responses
- Anthropic Messages
- Gemini `generateContent` / `streamGenerateContent`

Current scope is intentionally narrow:

- no protocol conversion
- SQLite persistence via SQLAlchemy ORM
- admin login
- channel management
- model-group aggregation
- gateway API keys managed in settings
- request logs and overview metrics

## Current Product Shape

Management UI:

- `/login`
- `/dashboard`
- `/dashboard/requests`
- `/dashboard/channels`
- `/dashboard/groups`
- `/dashboard/settings`

Gateway endpoints:

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/messages`
- `POST /v1beta/models/{model}:generateContent`
- `POST /v1beta/models/{model}:streamGenerateContent`

Management API:

- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/overview`
- `GET /api/request-logs`
- `GET /api/providers`
- `POST /api/providers`
- `PUT /api/providers/{provider_id}`
- `DELETE /api/providers/{provider_id}`
- `GET /api/router`
- `POST /api/router/preview`
- `GET /api/model-groups`
- `POST /api/model-groups`
- `PUT /api/model-groups/{group_id}`
- `DELETE /api/model-groups/{group_id}`
- `GET /api/settings`
- `PUT /api/settings`

## Stack

- Backend: FastAPI, HTTPX, SQLAlchemy 2.x, SQLite
- Frontend: Next.js App Router, React 19, TypeScript, TanStack Query, pnpm

## Run Backend

Use the `temp` conda environment.

```powershell
conda activate temp
cd D:\Projects\PYprojects\lens
python -m pip install -e .[dev]
python -m lens.main
```

Default backend address:

- `http://127.0.0.1:18080`

## Run Frontend

```powershell
conda activate temp
cd D:\Projects\PYprojects\lens\ui
pnpm install
pnpm dev
```

Default frontend address:

- `http://127.0.0.1:3000`

## Default Admin

On first startup the system creates:

- username: `admin`
- password: `admin`

Change `LENS_AUTH_SECRET_KEY` and the default admin password before any non-local use.

## Environment Variables

Supported backend configuration:

```env
LENS_HOST=127.0.0.1
LENS_PORT=18080
LENS_DATABASE_URL=sqlite+aiosqlite:///data/lens.db
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

## Routing Rules

Lens routes only within the same native protocol family.

Routing flow:

1. Authenticate the incoming gateway API key.
2. Read requested protocol and model.
3. If the model exactly matches a model-group name under the same protocol, use that group strategy and provider pool.
4. Otherwise fall back to provider-level model matching.
5. Route with `round_robin`, `weighted`, or `failover`.

Provider-level aggregation supports regex via `model_patterns`.

Example:

```text
^claude-opus-4-6$
^claude-opus-.*$
```

If you create a model group named `claude-opus-4-6`, that exact external name can map to a specific internal provider pool regardless of provider regexes.

## Downstream Gateway Access

Create one or more gateway API keys in `/dashboard?view=settings`, then call Lens with one of:

- `Authorization: Bearer <gateway-secret>`
- `x-api-key: <gateway-secret>`
- `x-goog-api-key: <gateway-secret>`

Example OpenAI Chat call:

```bash
curl http://127.0.0.1:18080/v1/chat/completions \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hello"}]}'
```

## What Is Implemented

- Admin authentication
- SQLite persistence with SQLAlchemy ORM
- CRUD for providers, model groups, settings
- Model-group routing and provider regex matching
- Native relay for OpenAI Chat, OpenAI Responses, Anthropic, Gemini
- Gateway API key authentication on `/v1/*` via settings
- Request logs and overview metrics in the admin UI

## What Is Not Implemented Yet

- Protocol conversion
- active health probing and circuit breaker logic
- upstream model sync
- cost accounting
- Alembic migrations
- multi-admin RBAC
