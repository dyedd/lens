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

Self-hosted multi-protocol LLM gateway that organizes providers by site, Base URL, credential, and protocol config, then exposes one unified entry to clients.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ Clients                                                              │
│ OpenAI SDK / Anthropic SDK / Gemini SDK / curl                       │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ Lens Base URL + sk-lens-...
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Lens Gateway                                                         │
│                                                                      │
│  Multi-protocol entry                                                │
│  /v1/chat/completions                                                │
│  /v1/messages                                                        │
│  /v1/responses                                                       │
│  /v1/embeddings                                                      │
│  /v1/rerank                                                          │
│  /v1beta/models/{model}:generateContent                              │
│                                                                      │
│  Request resolution                                                  │
│  - Validate gateway key                                              │
│  - Resolve client protocol and required model name                   │
│  - Match model group; routed groups may point to execution groups    │
│                                                                      │
│  Routing plan                                                        │
│  - Model group item: runtime channel + credential + upstream model   │
│  - Strategy: round robin / failover                                  │
│  - Protocol conversion: OpenAI Chat -> Anthropic / Responses         │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Admin configuration                                                  │
│                                                                      │
│  Site                                                                │
│  ├─ Base URLs: each URL declares supported protocols                  │
│  ├─ Credentials: one site can keep multiple API keys                  │
│  └─ Protocol configs: Base URL + default credential + protocols       │
│     plus headers, proxy, parameter overrides, and match rules         │
│                                                                      │
│  Discovered / manual models                                          │
│  - Models belong to protocol configs and keep protocol, credential,    │
│    and upstream model name                                            │
│  - Model discovery prefers a single /v1/models request                │
│                                                                      │
│  Model groups                                                        │
│  - Declare entry protocols, strategy, and optional execution group   │
│  - Items bind to: runtime channel + credential + upstream model      │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Candidate expansion and load balancing                               │
│                                                                      │
│  Runtime channel = protocol config + one protocol                     │
│  Route candidate = runtime channel + credential + upstream model     │
│                                                                      │
│  Round robin: smooth rotation across candidates                      │
│  Failover: try model group items in order, then switch credential or │
│  channel                                                             │
│                                                                      │
│  Cooldown scope                                                      │
│  401 / 403 cool the key; model faults cool only the upstream model    │
│  The channel is unavailable only when no key-model binding remains   │
│                                                                      │
│  Request logs                                                        │
│  Record lifecycle, tokens, cost, User-Agent, attempt chain, errors   │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
        ┌──────────────┬──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────────┐
   │ OpenAI  │    │Anthropic│    │ Gemini  │    │Compatible│
   └─────────┘    └─────────┘    └─────────┘    └──────────┘
```

## Features

- Unified entry: One Base URL and one gateway key for OpenAI / Anthropic / Gemini / Rerank entry protocols
- Site management: Configure multiple Base URLs, credentials, and protocol configs per site, with model discovery, manual models, and batch import
- Model group routing: Build candidates from runtime channel + credential + upstream model, with round robin, failover, and reusable execution groups
- Protocol conversion: Forward OpenAI Chat to Anthropic Messages or OpenAI Responses
- Request logs: Track protocol, model, latency, tokens, cost, User-Agent, and every upstream attempt
- Config backup: Export/import sites, model groups, settings, pricing, cron jobs, and stats; optionally include gateway keys and request logs

## Screenshots

| Overview                                              | Request Logs                                                  |
| ----------------------------------------------------- | ------------------------------------------------------------- |
| <img src="./screenshots/overview.png" alt="Overview"> | <img src="./screenshots/request-logs.png" alt="Request Logs"> |

| Channels                                              | Model Groups                                                  |
| ----------------------------------------------------- | ------------------------------------------------------------- |
| <img src="./screenshots/channels.png" alt="Channels"> | <img src="./screenshots/model-groups.png" alt="Model Groups"> |

| Settings                                              | API Keys                                              |
| ----------------------------------------------------- | ----------------------------------------------------- |
| <img src="./screenshots/settings.png" alt="Settings"> | <img src="./screenshots/api-keys.png" alt="API Keys"> |

| Scheduled Tasks                                                     | Backup & Restore                                               |
| ------------------------------------------------------------------- | -------------------------------------------------------------- |
| <img src="./screenshots/scheduled-tasks.png" alt="Scheduled Tasks"> | <img src="./screenshots/backups.png" alt="Backup and Restore"> |

## Quick Start

### Docker Compose (Recommended)

```bash
mkdir lens && cd lens
curl -fsSLO https://raw.githubusercontent.com/dyedd/lens/main/scripts/docker/deploy.sh
sh deploy.sh
```

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

The first startup creates the `admin` account and stores its random password in `admin-password` under the container data directory. Read the initial password with:

```bash
docker compose exec app cat /app/data/admin-password
```

Visit `http://127.0.0.1:3000`, change the administrator password immediately after signing in, and delete `admin-password` from the data directory.

### Build Locally

```bash
sh scripts/docker/deploy.sh
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

### Local Development

Requires Python 3.11+, uv, and pnpm.
The command below generates a random signing key only when `.env` does not exist and does not overwrite existing configuration.

```bash
uv sync --extra dev --locked
cd ui && pnpm install && cd ..
uv run --no-sync python -c "import os, secrets; from pathlib import Path; path = Path('.env'); os.umask(0o077); path.exists() or path.write_text(f'LENS_AUTH_SECRET_KEY={secrets.token_hex(32)}\n', encoding='utf-8')"
uv run --no-sync lens db upgrade
uv run --no-sync lens seed-admin --username admin --generate-password
uv run --no-sync lens dev
```

Default local development ports:

- Next.js dev server: `http://127.0.0.1:3000`
- FastAPI backend: `http://127.0.0.1:18080`

You can also run them separately:

```bash
uv run --no-sync lens serve

cd ui
pnpm dev
```

## Usage

### 1. Add Upstream Sites

Open `/channels`, create a site, configure Base URLs, credentials, and protocol configs, then discover or manually add models.

- **Base URLs**: One site can maintain multiple upstream URLs and declare supported protocols for each URL.
- **Credentials**: One site can maintain multiple API keys so routing can switch at credential granularity.
- **Protocol configs**: Bind a Base URL, default credential, and protocol list, with headers, proxy, parameter overrides, and model match rules.
- **Models**: Models belong to protocol configs and can bind to different credentials in the same site.

Common Base URLs:

| Upstream type   | Base URL example                            | Protocol                               |
| --------------- | ------------------------------------------- | -------------------------------------- |
| OpenAI          | `https://api.openai.com`                    | OpenAI Chat / Responses / Embeddings   |
| Anthropic       | `https://api.anthropic.com`                 | Anthropic                              |
| Gemini          | `https://generativelanguage.googleapis.com` | Gemini                                 |
| NewAPI / Rerank | `https://newapi.example.com`                | Rerank (forwards to `POST /v1/rerank`) |

### 2. Create Model Groups

Open `/groups`, create a model group, select entry protocols, add upstream model candidates, and choose a routing strategy:

- **Round robin**: Smoothly rotate across model group candidates
- **Failover**: Prefer earlier members, then switch to the next credential or channel after failures
- **Execution group reuse**: A visible group can point to another execution model group and reuse its candidates and strategy

**Protocol conversion**: Lens can currently put OpenAI Chat upstream models into Anthropic or OpenAI Responses model groups and convert at runtime.

### 3. Issue Gateway Keys

Open `/api-keys`, create a key, copy `sk-lens-...` to clients.

### 4. Client Integration

Clients only need: Lens Base URL + Gateway API Key + Model group name.

## Tech Stack

| Layer    | Technologies                                                    |
| -------- | --------------------------------------------------------------- |
| Backend  | Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite / PostgreSQL |
| Frontend | Next.js 16, React 19, TypeScript, TanStack Query, shadcn/ui     |

## Configuration

### Backend Environment Variables

| Variable                         | Default                              | Description                                                                                             |
| -------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| `LENS_DATABASE_URL`              | `sqlite+aiosqlite:///./data/data.db` | Database URL; the Docker image uses `/app/data/data.db`                                                 |
| `LENS_AUTH_SECRET_KEY`           | None (required)                      | JWT signing key, at least 32 bytes when UTF-8 encoded; the Docker deployment script writes it to `.env` |
| `LENS_PORT`                      | Local `18080` / Docker `3000`        | Listen port; Docker Compose also maps host and container ports from this value                          |
| `LENS_MAX_CONNECTIONS`           | `200`                                | Maximum connections per direct or proxy pool; requires a restart                                        |
| `LENS_MAX_KEEPALIVE_CONNECTIONS` | `50`                                 | Maximum idle connections per direct or proxy pool; requires a restart                                   |

### Gateway Settings

Configure these values on `/settings`:

| Setting key                   | Default     | Description                                                                                                                                                                      |
| ----------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `auth_access_token_minutes`   | 720 minutes | Lifetime of newly issued login access tokens; range `1`–`525600`                                                                                                                  |
| `first_token_timeout_seconds` | 180 seconds | Shared budget for the first deliverable response: first meaningful output for streaming requests, or the full response for non-streaming requests; range `0`–`86400`, where `0` is unlimited |
| `stream_idle_timeout_seconds` | 180 seconds | Maximum wait between upstream chunks after the first meaningful streaming output; range `0`–`86400`, where `0` is unlimited                                                    |
| `max_request_body_bytes`      | `32000000`  | Maximum request body sent upstream; `0` is unlimited                                                                                                                             |

#### Cooldown and Health Scoring

Cooldown is applied first to the smallest resource identified by the error. `401` / `403` cool the current key; `404`, `429`, `5xx`, upstream `408`, gateway timeouts, and network errors cool the actual upstream model. Other models and keys on the same channel remain routable. Ordinary `4xx` responses other than `401` / `403` / `404` / `408` / `429` usually describe the current request and do not affect cooldown. Standard `Retry-After` on `429` / `503` immediately cools the current model and takes precedence over category defaults within the maximum cooldown cap; `0` means immediate recovery.

Channels do not maintain a separate cooldown timer. For every enabled key-model binding:

```text
binding available at = max(key cooldown deadline, model cooldown deadline)
channel available     = any binding is available now
channel recovers at   = min(all binding availability times)
```

The channel becomes unavailable only when no enabled key-model binding remains usable. Every configured model cooling and every enabled key cooling are two common cases; sparse bindings can also be exhausted by a combination of model and key cooldowns. The channel recovers as soon as one binding becomes usable, without an additional channel-level cooldown.

After a category reaches its failure threshold, cooldown uses exponential backoff. Concurrent failures that finish during the same cooldown do not amplify the backoff again:

```text
first cooldown = min(category initial cooldown, maximum cooldown)
next cooldown  = min(previous cooldown × backoff multiplier, maximum cooldown)
```

Before a category triggers cooldown, the failure window measures the gap between consecutive failures. After cooldown completes, the window starts when the target becomes available again. Failure counts and backoff state restart only after the target remains free of new failures for the full window, so an immediate post-cooldown failure correctly increases backoff instead of treating the cooldown wait itself as a stable period.

An initial cooldown of `0` disables that category and clears its consecutive-failure count and backoff state. A maximum cooldown of `0` disables all automatic cooldown. A successful request resets only the current model and the key that actually succeeded; an older in-flight success that started before a newer failure cannot clear the newer cooldown. Concurrent failures during the same cooldown do not extend cooldown or amplify backoff, but they still prevent an older in-flight success from clearing newer failure evidence. Targets become eligible directly when cooldown expires; there is no separate half-open probe.

Health scores use a sliding window keyed by channel and actual model. `ROUND_ROBIN` uses the score as a smooth weighted-round-robin weight and prefers healthier fallbacks, while `FAILOVER` preserves the configured model-group order:

```text
confidence   = min(1, window samples / full-confidence samples)
health score = 1 - failure rate × maximum penalty ratio × confidence
```

Cooldown and health windows are runtime state in the current Lens process. They reset on restart and are not shared across workers or instances. Updating the contents of an existing key clears that key's old state; changing a channel endpoint, protocol, or request-affecting channel configuration clears that channel's state; changing the global proxy or upstream header rules clears all runtime cooldown and health windows.

| Setting key                                  | Default | Description |
| -------------------------------------------- | ------- | ----------- |
| `circuit_breaker_threshold`                  | `3`     | Consecutive `5xx` failure threshold; positive integer; `503` with `Retry-After` triggers cooldown immediately |
| `circuit_breaker_failure_window_seconds`     | `300`   | Same-category failure gap before cooldown and failure-free stability period after recovery, range `1`–`604800`, independent of health scoring |
| `circuit_breaker_timeout_threshold`          | `2`     | Consecutive upstream `408` or gateway-timeout threshold; positive integer |
| `circuit_breaker_network_threshold`          | `2`     | Consecutive network-error threshold; positive integer |
| `circuit_breaker_cooldown`                   | `60`    | Initial `5xx` cooldown, range `0`–`604800` seconds |
| `circuit_breaker_auth_cooldown`              | `300`   | Initial key cooldown for `401` / `403`, range `0`–`604800` seconds |
| `circuit_breaker_not_found_cooldown`         | `300`   | Initial model cooldown for `404`, range `0`–`604800` seconds; affects only the current model when no broader fault domain is proven |
| `circuit_breaker_rate_limit_cooldown`        | `60`    | Initial model cooldown for `429`, range `0`–`604800` seconds |
| `circuit_breaker_timeout_cooldown`           | `60`    | Initial model cooldown for upstream `408` or gateway timeouts, range `0`–`604800` seconds |
| `circuit_breaker_network_cooldown`           | `60`    | Initial model cooldown for network errors, range `0`–`604800` seconds |
| `circuit_breaker_backoff_multiplier`         | `2`     | Subsequent cooldown multiplier, range `1`–`10` |
| `circuit_breaker_max_cooldown`               | `600`   | Hard cap for all automatic cooldowns, range `0`–`604800` seconds; `0` disables them |
| `health_scoring_enabled`                     | `true`  | Enables health-based ordering |
| `health_window_seconds`                      | `300`   | Per-model sliding-window duration, range `1`–`604800` seconds |
| `health_penalty_weight`                      | `0.5`   | Maximum health penalty ratio, range `0`–`1` |
| `health_min_samples`                         | `10`    | Samples required for full confidence; positive integer |

### Docker Compose

| Variable               | Default | Description                                                        |
| ---------------------- | ------- | ------------------------------------------------------------------ |
| `LENS_PORT`            | `3000`  | Container listen port and host port mapping (same value)           |
| `LENS_SKIP_DB_UPGRADE` | `0`     | Set to `1` to skip container startup migrations; upgrade the schema first |

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
uv run lens db upgrade  # upgrade to latest
uv run lens db downgrade  # downgrade one revision
uv run lens db revision -m "describe your change"  # create a migration
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
<summary>Rerank (curl)</summary>

```bash
curl http://127.0.0.1:3000/v1/rerank \
  -H "Authorization: Bearer sk-lens-..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-rerank-group",
    "query": "What is the capital of France?",
    "documents": [
      "Paris is the capital of France.",
      "Berlin is the capital of Germany.",
      "Madrid is the capital of Spain."
    ],
    "top_n": 3,
    "return_documents": true
  }'
```

The request body is forwarded as-is to the upstream `/v1/rerank` endpoint (e.g. NewAPI, Jina, Cohere-compatible services). Responses are returned unmodified, including `results[*].relevance_score / index / document`.

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
