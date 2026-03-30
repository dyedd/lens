# Lens

Lens is a Python + Next.js management console and LLM gateway.

Current product shape:

- Admin login
- Provider channel management
- Model group management
- Downstream gateway key management
- System settings management
- Native protocol relay for:
  - OpenAI Chat Completions
  - OpenAI Responses
  - Anthropic Messages
  - Gemini `generateContent` / `streamGenerateContent`
- SQLite persistence through SQLAlchemy ORM
- Model aggregation with regex-based matching

This project does not do protocol conversion. Routing stays inside each native protocol family.

## Stack

- Backend: FastAPI, SQLAlchemy, SQLite, HTTPX
- Frontend: Next.js App Router, React 19, TypeScript, pnpm, TanStack Query

## Admin surface

Routes implemented in the management UI:

- `/login`
- `/dashboard`
- `/dashboard/channels`
- `/dashboard/groups`
- `/dashboard/keys`
- `/dashboard/settings`

Default admin credentials on first startup:

- username: `admin`
- password: `admin`

Change the secret and default password before using this outside local development.

## Backend setup

Use the `temp` conda environment:

```powershell
conda activate temp
cd D:\Projects\PYprojects\lens
python -m pip install -e .
python -m lens.main
```

The backend listens on `http://127.0.0.1:8000` by default.

### Environment

Optional `.env` keys:

```env
LENS_HOST=127.0.0.1
LENS_PORT=8000
LENS_DATABASE_URL=sqlite+aiosqlite:///data/lens.db
LENS_AUTH_SECRET_KEY=change-me-in-production
LENS_AUTH_ALGORITHM=HS256
LENS_AUTH_ACCESS_TOKEN_MINUTES=720
LENS_ADMIN_DEFAULT_USERNAME=admin
LENS_ADMIN_DEFAULT_PASSWORD=admin
LENS_ANTHROPIC_VERSION=2023-06-01
LENS_REQUEST_TIMEOUT_SECONDS=180
LENS_CONNECT_TIMEOUT_SECONDS=10
```

## Frontend setup

```powershell
conda activate temp
cd D:\Projects\PYprojects\lens\web
pnpm install
pnpm dev
```

The frontend runs on `http://127.0.0.1:3000`.

`Next.js` rewrites `/api/*` to the FastAPI backend at `http://127.0.0.1:8000/api/*`.

## Gateway endpoints

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/messages`
- `POST /v1beta/models/{model}:generateContent`
- `POST /v1beta/models/{model}:streamGenerateContent`

## Management API

- `POST /api/auth/login`
- `GET /api/auth/me`
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
- `GET /api/gateway-keys`
- `POST /api/gateway-keys`
- `PUT /api/gateway-keys/{key_id}`
- `DELETE /api/gateway-keys/{key_id}`
- `GET /api/settings`
- `PUT /api/settings`

## Model aggregation

Each provider can define `model_patterns`, a list of regex patterns.

Example:

```text
^claude-opus-4-6$
^claude-opus-.*$
```

If a request comes in with `model: "claude-opus-4-6"`, the router filters the same-protocol provider pool by these regex rules before applying weighted round robin or failover.

If `model_patterns` is empty, routing falls back to exact `model_name` matching when a request includes `model`.

## Current scope

Implemented:

- Admin login
- Management backend shell
- CRUD for channels, model groups, gateway keys, settings
- Regex-based model matching
- SQLite persistence
- Native protocol relay for the four requested upstream families

Not implemented yet:

- Protocol conversion
- request logs and analytics UI
- price sync
- model sync from upstream
- circuit breaker and active health probing
- Alembic migrations
- multi-admin RBAC
