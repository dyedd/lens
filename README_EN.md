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
- Statistics are persisted by scheduled tasks to avoid high-frequency aggregate writes

### Management Console

Console pages:

- `/`: overview
- `/channels`: sites, channels, credentials, and models
- `/groups`: model groups, routing, and pricing
- `/requests`: request logs and details
- `/api-keys`: gateway API key management
- `/cronjobs`: scheduled tasks and log cleanup schedules
- `/backups`: configuration export and import
- `/settings`: system settings, site information, and account settings

## Tech Stack

| Layer            | Technologies                                                                               |
| ---------------- | ------------------------------------------------------------------------------------------ |
| Backend          | Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, SQLite                                     |
| Frontend         | Next.js 16, React 19, TypeScript, TanStack Query, shadcn/ui                                |
| Container        | Multi-stage build; Node is used only for frontend build; final image is `python:3.14-slim` |
| Package managers | pip, pnpm                                                                                  |

## Quick Start

### Docker Compose

Place `docker-compose.yml` in a deployment directory and create `.env`:

```bash
mkdir lens
cd lens
curl -fsSLO https://raw.githubusercontent.com/dyedd/lens/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/dyedd/lens/main/.env.example
cp .env.example .env
```

Before starting Lens, edit `.env` and at least change `LENS_AUTH_SECRET_KEY`.

To change the data directory, edit only the host path on the left side of `volumes`; keep `/app/data` unchanged:

```yaml
volumes:
  - ./data:/app/data
```

Pull and start the published image:

```bash
docker compose pull
docker compose up -d
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
- The container listens on `0.0.0.0:3000`; do not use `PORT` or `HOSTNAME` to configure Lens
- Set `LENS_SKIP_DB_UPGRADE=1` to skip automatic migrations on startup

### Docker Run

```bash
mkdir -p data

docker run -d --name lens \
  --env-file .env \
  -p 3000:3000 \
  -v "$(pwd)/data:/app/data" \
  ghcr.io/dyedd/lens:latest
```

The `docker run` example assumes the current directory already contains a `.env` copied from `.env.example` and edited for deployment. Do not set `LENS_PORT` to the local development port in that file. Containers should keep `LENS_HOST=0.0.0.0` and `LENS_PORT=3000`.

To build locally:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

`docker-compose.local.yml` must be in the same directory as `docker-compose.yml`. The repository already includes this file; it changes the image name to `lens:local` and builds from the current source tree.

If you are building from a standalone deployment directory, create `docker-compose.local.yml` manually:

```yaml
services:
  app:
    image: lens:local
    build:
      context: .
      dockerfile: Dockerfile
```

Put the project source tree in the same directory, then run:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

You can also build manually and run without Compose:

```bash
docker build -t lens:local .

mkdir -p data

docker run -d --name lens \
  --env-file .env \
  -p 3000:3000 \
  -v "$(pwd)/data:/app/data" \
  lens:local
```

### Local Development

Install the backend:

```bash
pip install -e ".[dev]"
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

Default local development ports:

- Next.js dev server: `http://127.0.0.1:3000`; if the port is already in use, follow the URL printed by Next.js
- FastAPI backend: `http://127.0.0.1:18080`
- `lens dev` keeps frontend HMR, backend reload, and proxies frontend API calls to the backend

You can also run them separately:

```bash
lens serve --reload

cd ui
pnpm dev
```

## First-Time Setup

After deployment and login, configure Lens in this order. The core workflow is: add upstream channels, put upstream models into model groups, then issue gateway API keys to clients.

### 1. Update the administrator account

Open `/settings`:

- Change the default administrator password
- Configure the site name, logo, application time zone, CORS, and global proxy as needed
- The default application time zone is `Asia/Shanghai`; it affects request log timestamps, statistics buckets, today windows, scheduled task run times, and backup filenames

### 2. Add upstream sites and channels

Open `/channels` and create a site:

1. Enter a site name, for example `OpenAI`, `Anthropic`, `Gemini`, or the name of an internal compatible service
2. Add a Base URL, for example `https://api.openai.com`
3. Add an upstream API key
4. Add a protocol config and choose the protocol the upstream actually supports, for example `OpenAI Chat`
5. Discover models from the upstream, or enter model names manually
6. Keep the models you want to use enabled

Common Base URL examples:

| Upstream type             | Base URL example                      | Protocol         |
| ------------------------- | ------------------------------------- | ---------------- |
| OpenAI                    | `https://api.openai.com`              | OpenAI Chat      |
| OpenAI-compatible service | `https://example.com`                 | OpenAI Chat      |
| Anthropic                 | `https://api.anthropic.com`           | Anthropic        |
| Gemini                    | `https://generativelanguage.googleapis.com` | Gemini |

For upstream Base URLs, the recommended value is the service root. Lens automatically appends `/v1` or `/v1beta` based on the selected protocol, and it also accepts addresses that already include `/v1` or `/v1beta`.

### 3. Create model groups

Open `/groups` and create a model group. The model group name is the `model` value clients will request.

For example, to expose `gpt-4o-mini` to clients:

1. Set the model group name to `gpt-4o-mini`
2. Choose the client-facing protocol, for example `OpenAI Chat`
3. Add one or more upstream models from the candidate list
4. Choose a routing strategy:
   - `round_robin`: distribute requests across enabled members with smooth weighted round robin
   - `failover`: prefer earlier members and switch to later members after failures
5. Save the group, then use route preview to confirm which upstreams can be selected

The model group protocol means the client-facing protocol. Members do not always need to use the exact same upstream protocol. Lens can currently put OpenAI Chat upstream models into Anthropic or OpenAI Responses model groups and convert requests and responses at runtime.

Examples:

| Client-facing protocol | Model group name | Allowed upstream members                         |
| ---------------------- | ---------------- | ------------------------------------------------ |
| OpenAI Chat            | `gpt-4o-mini`    | OpenAI Chat upstream models                      |
| Anthropic Messages     | `claude-alias`   | Anthropic upstream models, or OpenAI Chat upstream models |
| OpenAI Responses       | `responses-main` | OpenAI Responses upstream models, or OpenAI Chat upstream models |
| Gemini                 | `gemini-main`    | Gemini upstream models                           |

### 4. Maintain model pricing

Use the pricing area in `/groups`:

- Sync prices from `models.dev`
- Or maintain input, output, and cache prices manually
- Request logs and dashboard cost estimates use these prices

### 5. Create gateway API keys

Open `/api-keys`:

1. Create a gateway API key
2. Optionally restrict allowed model groups, maximum spend, and expiration time
3. Give the generated `sk-lens-...` key to downstream clients

Clients only need:

- Lens Base URL
- Gateway API key
- Model group name

### 6. Call and troubleshoot

After clients start calling Lens:

- Use `/requests` to inspect request status, protocol, model group, upstream model, latency, tokens, cost, and errors
- Use `/` to inspect request volume, success rate, latency, and model trends
- Use `/cronjobs` to configure log cleanup, stats persistence, model price sync, and other scheduled tasks
- Use `/backups` to export configuration bundles; back up before migrations or upgrades

## Client Integration

Complete the first-time setup first so you have a model group and a gateway API key, then point downstream clients to Lens.

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

| Variable                         | Default                               | Description                                              |
| -------------------------------- | ------------------------------------- | -------------------------------------------------------- |
| `LENS_HOST`                      | `127.0.0.1`                           | Backend listen host; Docker sets it to `0.0.0.0`         |
| `LENS_PORT`                      | `18080`                               | Backend listen port; Docker sets it to `3000`            |
| `LENS_DATABASE_URL`              | `sqlite+aiosqlite:///./data/data.db`  | Database URL; defaults to `data` under the working dir    |
| `LENS_AUTH_SECRET_KEY`           | development default                   | JWT signing key; must be changed in production           |
| `LENS_AUTH_ACCESS_TOKEN_MINUTES` | `720`                                 | Console session lifetime                                 |
| `LENS_REQUEST_TIMEOUT_SECONDS`   | `180`                                 | Upstream request timeout                                 |
| `LENS_CONNECT_TIMEOUT_SECONDS`   | `10`                                  | Upstream connection timeout                              |
| `LENS_MAX_CONNECTIONS`           | `200`                                 | HTTP connection pool size                                |
| `LENS_MAX_KEEPALIVE_CONNECTIONS` | `50`                                  | HTTP keep-alive pool size                                |
| `LENS_ANTHROPIC_VERSION`         | `2023-06-01`                          | Anthropic version header                                 |
| `LENS_UI_STATIC_DIR`             | empty                                 | Static frontend directory; Docker sets it to `/app/ui`   |
| `LENS_SKIP_DB_UPGRADE`           | `0`                                   | Set to `1` to skip Docker startup migration              |
| `LENS_UI_BACKEND_BASE_URL`       | `http://127.0.0.1:18080`              | Local Next.js dev/standalone proxy target                |

The backend listen address and port are controlled by `LENS_HOST` and `LENS_PORT`; generic `HOSTNAME` and `PORT` do not affect them.

The Docker image and `docker-compose.yml` explicitly set the database URL to `sqlite+aiosqlite:////app/data/data.db`; local development defaults to `sqlite+aiosqlite:///./data/data.db`. A deployment `.env` does not need `LENS_DATABASE_URL`, which avoids overriding the container path.

Lens application time zone is not an environment variable. Choose it in `/settings`; the default is `Asia/Shanghai`. Request log timestamps, today windows, trend buckets, backup filenames, and other in-app time displays use this setting.

More runtime settings, including CORS, proxy, circuit breaker, health scoring, site name, and logo, can be changed in `/settings`; log retention and cleanup schedules are changed in `/cronjobs`.

## Configuration Backup and Migration

The management console can export and import configuration bundles, including:

- Sites, Base URLs, credentials, protocol bindings, and model lists
- Model groups and routing strategies
- Gateway API keys
- Model prices
- System settings
- Cron jobs
- Optional statistics snapshots and request logs

Back up the current data directory before importing a configuration bundle.

## Security Notes

- Change `LENS_AUTH_SECRET_KEY` in production
- Change the default administrator username or password after first login
- Create separate gateway API keys for different clients
- Do not commit `.env`, `data/`, or database files
- Put Lens behind an HTTPS reverse proxy when exposing it to the public internet

## Acknowledgments

Lens was inspired by the following projects and community discussions:

- [bestruirui/octopus](https://github.com/bestruirui/octopus)
- [cita-777/metapi](https://github.com/cita-777/metapi)
- [caidaoli/ccLoad](https://github.com/caidaoli/ccLoad)
- [Linux DO community](https://linux.do/)
