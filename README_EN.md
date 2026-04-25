<p align="center">
  <img src="./ui/public/logo.svg" alt="Lens" width="88" height="88">
</p>

<h1 align="center">Lens</h1>

<p align="center">
  A self-hosted multi-provider LLM gateway and management console that exposes scattered model providers through one endpoint, one set of gateway API keys, and manageable model names.
</p>

<p align="center">
  <a href="./README.md">简体中文</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white" alt="FastAPI 0.115+">
  <img src="https://img.shields.io/badge/Next.js-16-black?logo=nextdotjs" alt="Next.js 16">
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=111" alt="React 19">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License">
</p>

Lens is a self-hosted multi-provider LLM gateway with a web management console. It lets you expose scattered upstream model providers through one gateway endpoint, one set of gateway API keys, and manageable external model names.

## What Lens Solves

- Avoid configuring many provider keys and Base URLs in every downstream tool
- Route one public model name to multiple upstream channels
- Access OpenAI, Anthropic, Gemini, and OpenAI-compatible providers through one gateway
- Track request logs, token usage, latency, success rate, and estimated cost
- Export and import gateway configuration for backup or migration

## Core Features

### Unified Protocol Entry Points

Lens exposes common LLM API routes:

| Client protocol              | Route                                          |
| ---------------------------- | ---------------------------------------------- |
| OpenAI Chat Completions      | `/v1/chat/completions`                         |
| OpenAI Responses             | `/v1/responses`                                |
| Anthropic Messages           | `/v1/messages`                                 |
| OpenAI Models                | `/v1/models`                                   |
| Gemini generateContent       | `/v1beta/models/{model}:generateContent`       |
| Gemini streamGenerateContent | `/v1beta/models/{model}:streamGenerateContent` |

Supported gateway authentication headers:

```http
Authorization: Bearer <gateway-key>
x-api-key: <gateway-key>
x-goog-api-key: <gateway-key>
```

### Upstream Site and Channel Management

- Configure multiple Base URLs, credentials, protocols, and model lists per site
- Manage OpenAI Chat, OpenAI Responses, Anthropic, and Gemini channels
- Discover models from upstream providers
- Configure global proxy, CORS, site name, and site logo at runtime

### Model Groups and Routing

- A model group is the public model name exposed to downstream clients
- Current routing strategies:
  - `round_robin`: smooth round-robin distribution
  - `failover`: prefer earlier channels and switch after failures
- Health windows, failure penalties, and circuit breaker cooldown reduce traffic to unhealthy channels
- Route preview and router snapshots help explain where requests will go

### Protocol Conversion

Same-protocol requests are passed through directly. Current cross-protocol conversions:

| Upstream channel protocol | Client protocol    | Behavior                                                                        |
| ------------------------- | ------------------ | ------------------------------------------------------------------------------- |
| OpenAI Chat               | Anthropic Messages | Convert `/v1/messages` requests to Chat Completions and convert responses back  |
| OpenAI Chat               | OpenAI Responses   | Convert `/v1/responses` requests to Chat Completions and convert responses back |

### Observability and Cost

- Request logs include protocol, model, status, latency, token usage, errors, and attempt chains
- Dashboard metrics include request volume, success rate, average latency, token trends, and model analytics
- Model pricing can be synced from `models.dev` or maintained manually
- Statistics are persisted on a configurable interval to avoid high-frequency writes

### Management Console

Console pages:

- `/`: overview
- `/channels`: sites, channels, credentials, and models
- `/groups`: model groups, routing, and pricing
- `/requests`: request logs and details
- `/settings`: gateway API keys, system settings, import/export, and account settings

## Tech Stack

| Layer            | Technologies                                                                               |
| ---------------- | ------------------------------------------------------------------------------------------ |
| Backend          | Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, SQLite                                     |
| Frontend         | Next.js 16, React 19, TypeScript, TanStack Query, shadcn/ui                                |
| Container        | Multi-stage build; Node is used only for frontend build; final image is `python:3.14-slim` |
| Package managers | pip, pnpm                                                                                  |

## Quick Start

### Docker Compose

Copy the environment example:

```bash
cp .env.example .env
```

Start Lens:

```bash
docker compose up --build
```

Open:

- Console and gateway: `http://127.0.0.1:3000`
- Health check: `http://127.0.0.1:3000/healthz`

Default administrator:

```text
username: admin
password: admin
```

Change the default administrator password immediately after first login, and change `LENS_AUTH_SECRET_KEY` in production.

Docker notes:

- A single container serves the static frontend and the FastAPI gateway
- Startup runs `lens db upgrade`
- Startup attempts to seed the default administrator and skips it if an admin already exists
- `./data` is mounted to `/app/data` for SQLite persistence
- Set `LENS_SKIP_DB_UPGRADE=1` to skip automatic migrations on startup

### Docker Run

```bash
docker run -d --name lens \
  -p 3000:3000 \
  --env-file .env \
  -v ./data:/app/data \
  ghcr.io/dyedd/lens:latest
```

To build locally:

```bash
docker build -t lens:local .

docker run -d --name lens \
  -p 3000:3000 \
  --env-file .env \
  -v ./data:/app/data \
  lens:local
```

### Local Development

Install the backend:

```bash
pip install -e .[dev]
```

Install frontend dependencies:

```bash
cd ui
pnpm install
cd ..
```

Initialize the database and administrator:

```bash
lens db upgrade
lens seed-admin --username admin --password admin
```

Start both development servers:

```bash
lens dev
```

Local development ports:

- Next.js dev server: `http://127.0.0.1:3000`
- FastAPI backend: `http://127.0.0.1:18080`
- `lens dev` keeps frontend HMR, backend reload, and proxies frontend API calls to the backend

You can also run them separately:

```bash
lens serve --reload

cd ui
pnpm dev
```

## Client Integration

Create a gateway API key in the settings page, then point downstream clients to Lens.

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

Example environment:

```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:3000
ANTHROPIC_AUTH_TOKEN=sk-lens-...
ANTHROPIC_MODEL=your-anthropic-group
ANTHROPIC_SMALL_FAST_MODEL=your-anthropic-group
```

### Codex

Example `~/.codex/config.toml`:

```toml
model = "your-model-group"
model_provider = "lens"

[model_providers.lens]
name = "Lens"
base_url = "http://127.0.0.1:3000/v1"
```

Example `~/.codex/auth.json`:

```json
{
  "OPENAI_API_KEY": "sk-lens-..."
}
```

## Routing Rules

Request flow:

1. Validate the gateway API key
2. Detect the client protocol from the request path
3. Read the requested model name from the request body
4. Prefer an exact model group match and use that group's channel pool and strategy
5. Run protocol conversion only when the matched group supports the client/upstream pair
6. If no model group matches, fall back to channel-level model matching; this path only matches the same protocol
7. Select an upstream channel via `round_robin` or `failover`
8. Record logs, tokens, cost, latency, and attempt results

## Database Migrations

```bash
lens db upgrade                               # upgrade to latest
lens db downgrade                             # downgrade one revision
lens db revision -m "describe your change"    # create a migration
lens db current                               # show current revision
lens db history                               # show migration history
lens db stamp head                            # mark database as latest
```

## Environment Variables

Backend configuration uses the `LENS_` prefix and also supports `.env` files. Local frontend development additionally reads `LENS_UI_BACKEND_BASE_URL` as the proxy target.

| Variable                         | Default                            | Description                                      |
| -------------------------------- | ---------------------------------- | ------------------------------------------------ |
| `LENS_HOST`                      | `127.0.0.1`                        | Backend listen host; Docker sets it to `0.0.0.0` |
| `LENS_PORT`                      | `18080`                            | Backend listen port; Docker sets it to `3000`    |
| `LENS_DATABASE_URL`              | `sqlite+aiosqlite:///data/data.db` | Database URL                                     |
| `LENS_AUTH_SECRET_KEY`           | development default                | JWT signing key; must be changed in production   |
| `LENS_AUTH_ACCESS_TOKEN_MINUTES` | `720`                              | Console session lifetime                         |
| `LENS_REQUEST_TIMEOUT_SECONDS`   | `180`                              | Upstream request timeout                         |
| `LENS_CONNECT_TIMEOUT_SECONDS`   | `10`                               | Upstream connection timeout                      |
| `LENS_MAX_CONNECTIONS`           | `200`                              | HTTP connection pool size                        |
| `LENS_MAX_KEEPALIVE_CONNECTIONS` | `50`                               | HTTP keep-alive pool size                        |
| `LENS_ANTHROPIC_VERSION`         | `2023-06-01`                       | Anthropic version header                         |
| `LENS_UI_STATIC_DIR`             | empty                              | Static frontend directory; used inside Docker    |
| `LENS_UI_BACKEND_BASE_URL`       | `http://127.0.0.1:18080`           | Local Next.js dev proxy target                   |
| `LENS_SKIP_DB_UPGRADE`           | `0`                                | Set to `1` to skip Docker startup migration      |

More runtime settings, including CORS, proxy, log retention, circuit breaker, health scoring, site name, and logo, can be changed in the management console.

## Configuration Backup and Migration

The management console can export and import configuration bundles, including:

- Sites, Base URLs, credentials, protocol bindings, and model lists
- Model groups and routing strategies
- Gateway API keys
- Model prices
- System settings
- Optional statistics snapshots and request logs

Back up the current data directory before importing a configuration bundle.

## Security Notes

- Change `LENS_AUTH_SECRET_KEY` in production
- Change the default administrator username or password after first login
- Create separate gateway API keys for different clients
- Do not commit `.env`, `data/`, or database files
- Put Lens behind an HTTPS reverse proxy when exposing it to the public internet
