<p align="center">
  <img src="./ui/public/logo.svg" alt="Lens" width="88" height="88">
</p>

<h1 align="center">Lens</h1>

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

Self-hosted LLM gateway for managing multiple model providers.

## Architecture

```
┌─────────────┐
│   Clients   │  OpenAI SDK / Anthropic SDK / curl
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────┐
│              Lens Gateway                       │
│  ┌──────────────────────────────────────────┐  │
│  │  /v1/chat/completions                    │  │
│  │  /v1/messages                            │  │
│  │  /v1/responses                           │  │
│  │  /v1/embeddings                          │  │
│  │  /v1beta/models/{model}:generateContent  │  │
│  └──────────────────────────────────────────┘  │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │  Routing Layer                           │  │
│  │  - Model group matching                  │  │
│  │  - Load balancing (round_robin/failover) │  │
│  │  - Protocol conversion                   │  │
│  │  - Health checks                         │  │
│  └──────────────────────────────────────────┘  │
└────────┬────────────────────────────────────────┘
         │
         ├─────────────┬─────────────┬─────────────┐
         ▼             ▼             ▼             ▼
    ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
    │ OpenAI  │  │Anthropic│  │ Gemini  │  │Compatible│
    └─────────┘  └─────────┘  └─────────┘  └─────────┘
```

## Features

- Unified entry: One Base URL, one API Key, supports OpenAI / Anthropic / Gemini protocols
- Load balancing: round_robin or failover strategies
- Protocol conversion: Forward OpenAI Chat to Anthropic Messages or OpenAI Responses
- Request logs: Track protocol, model, latency, tokens, cost
- Config backup: Export/import sites, channels, model groups, pricing

## Quick Start

### Docker Compose (Recommended)

```bash
mkdir lens && cd lens
curl -fsSLO https://raw.githubusercontent.com/dyedd/lens/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/dyedd/lens/main/.env.example
cp .env.example .env
```

Edit `.env` and configure as needed. You must change `LENS_AUTH_SECRET_KEY` in production.

To change the data directory, edit only the host path on the left side of `volumes`; keep `/app/data` unchanged:

```yaml
volumes:
  - ./data:/app/data
```

Start:

```bash
docker compose pull
docker compose up -d
```

Visit `http://127.0.0.1:3000`, default credentials `admin/admin`. Change the default administrator password immediately after first login.

### Docker Run

```bash
mkdir -p data

docker run -d --name lens \
  --env-file .env \
  -p 3000:3000 \
  -v "$(pwd)/data:/app/data" \
  ghcr.io/dyedd/lens:latest
```

### Build Locally

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

`docker-compose.local.yml` must be in the same directory as `docker-compose.yml`. The repository includes this file, which changes the image name to `lens:local` and builds from the current source tree.

If building from a standalone deployment directory, create `docker-compose.local.yml` manually:

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

```bash
pip install -e ".[dev]"
cd ui && pnpm install && cd ..
lens db upgrade
lens seed-admin --username admin --password admin
lens dev
```

Default local development ports:
- Next.js dev server: `http://127.0.0.1:3000`
- FastAPI backend: `http://127.0.0.1:18080`

You can also run them separately:

```bash
lens serve --reload

cd ui
pnpm dev
```

## Usage

### 1. Add Upstream Sites

Open `/channels`, create a site, fill in Base URL and API Key, discover or manually add models.

Common Base URLs:

| Upstream type             | Base URL example                      | Protocol         |
| ------------------------- | ------------------------------------- | ---------------- |
| OpenAI                    | `https://api.openai.com`              | OpenAI Chat / Responses / Embeddings |
| Anthropic                 | `https://api.anthropic.com`           | Anthropic        |
| Gemini                    | `https://generativelanguage.googleapis.com` | Gemini |

### 2. Create Model Groups

Open `/groups`, create a model group, select protocol, add upstream models, choose routing strategy:

- **round_robin**: Distribute requests with smooth weighted round robin
- **failover**: Prefer earlier members, switch after failures

**Protocol conversion**: Lens can currently put OpenAI Chat upstream models into Anthropic or OpenAI Responses model groups and convert at runtime.

### 3. Issue Gateway Keys

Open `/api-keys`, create a key, copy `sk-lens-...` to clients.

### 4. Client Integration

Clients only need: Lens Base URL + Gateway API Key + Model group name.

## Tech Stack

| Layer    | Technologies                                                   |
| -------- | -------------------------------------------------------------- |
| Backend  | Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite / PostgreSQL |
| Frontend | Next.js 16, React 19, TypeScript, TanStack Query, shadcn/ui    |

## Environment Variables

Core variables:

| Variable                         | Default                               | Description                                      |
| -------------------------------- | ------------------------------------- | ------------------------------------------------ |
| `LENS_HOST`                      | `127.0.0.1`                           | Backend listen host; Docker sets it to `0.0.0.0` |
| `LENS_PORT`                      | `18080`                               | Backend listen port; Docker sets it to `3000`    |
| `LENS_DATABASE_URL`              | `sqlite+aiosqlite:///./data/data.db`  | Database URL; defaults to SQLite, can point to external PostgreSQL |
| `LENS_AUTH_SECRET_KEY`           | `lens-dev-jwt-signing-secret-2026-default` | JWT signing key; must be changed in production |
| `LENS_REQUEST_TIMEOUT_SECONDS`   | `180`                                 | Upstream request timeout                         |

### PostgreSQL Configuration

PostgreSQL URL format:

```
postgresql+psycopg://username:password@host:port/database
```

Example:

```bash
LENS_DATABASE_URL=postgresql+psycopg://lens:password@postgres.example.com:5432/lens
```

**Configuration Tips for 1Panel and Other Containerized Environments**:

If Lens and PostgreSQL run on the same server, put both containers in the same Docker network (such as 1Panel's `1panel-network`), and use the PostgreSQL container name as the host:

```bash
LENS_DATABASE_URL=postgresql+psycopg://lens:password@postgresql:5432/lens
```

The first `lens` is the database username, the last `lens` is the database name, and `postgresql` is the PostgreSQL container name; adjust it to your actual container name.

**SQLite is suitable for local testing and lightweight deployments. Use PostgreSQL for production or high-concurrency scenarios.**

## Database Migrations

```bash
lens db upgrade                               # upgrade to latest
lens db downgrade                             # downgrade one revision
lens db revision -m "describe your change"    # create a migration
```

To move from SQLite to PostgreSQL: export config at `/backups` → change `LENS_DATABASE_URL` → start Lens → import config.

## Client Integration

<details>
<summary>OpenAI SDK (Python)</summary>

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
</details>

<details>
<summary>Anthropic SDK (Python)</summary>

```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://127.0.0.1:3000",
    api_key="sk-lens-...",
)

message = client.messages.create(
    model="your-anthropic-group",
    max_tokens=256,
    messages=[{"role": "user", "content": "hello"}],
)
print(message.content[0].text)
```
</details>

<details>
<summary>OpenAI Chat (curl)</summary>

```bash
curl http://127.0.0.1:3000/v1/chat/completions \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model-group",
    "messages": [{"role": "user", "content": "hello"}]
  }'
```
</details>

<details>
<summary>Anthropic Messages (curl)</summary>

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
</details>

<details>
<summary>OpenAI Responses (curl)</summary>

```bash
curl http://127.0.0.1:3000/v1/responses \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-responses-group",
    "input": "hello"
  }'
```
</details>

<details>
<summary>OpenAI Embeddings (curl)</summary>

```bash
curl http://127.0.0.1:3000/v1/embeddings \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-embedding-group",
    "input": "hello world"
  }'
```
</details>

<details>
<summary>Gemini (curl)</summary>

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
</details>

<details>
<summary>Claude Code</summary>

```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:3000
ANTHROPIC_AUTH_TOKEN=sk-lens-...
ANTHROPIC_MODEL=your-anthropic-group
ANTHROPIC_SMALL_FAST_MODEL=your-anthropic-group
```
</details>

<details>
<summary>Codex</summary>

`~/.codex/config.toml`:

```toml
model = "your-model-group"
model_provider = "lens"

[model_providers.lens]
name = "Lens"
base_url = "http://127.0.0.1:3000/v1"
```

`~/.codex/auth.json`:

```json
{
  "OPENAI_API_KEY": "sk-lens-..."
}
```
</details>

## Acknowledgments

- [bestruirui/octopus](https://github.com/bestruirui/octopus)
- [cita-777/metapi](https://github.com/cita-777/metapi)
- [caidaoli/ccLoad](https://github.com/caidaoli/ccLoad)
- [Linux DO community](https://linux.do/)

## License

MIT
