# syntax=docker/dockerfile:1

ARG NODE_IMAGE=node:22-bookworm-slim
ARG PNPM_VERSION=10.17.1
ARG UV_VERSION=0.11.28

FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS ui-base

WORKDIR /app/ui

ARG PNPM_VERSION
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH

RUN corepack enable pnpm \
    && corepack prepare pnpm@${PNPM_VERSION} --activate

FROM ui-base AS ui-deps

COPY ui/pnpm-lock.yaml ui/pnpm-workspace.yaml ./
RUN pnpm fetch

COPY ui/package.json ./
RUN pnpm install --frozen-lockfile --offline

FROM ui-base AS ui-builder

COPY --from=ui-deps /app/ui/node_modules ./node_modules
COPY ui ./

ENV NODE_ENV=production

RUN pnpm build

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:3.11-slim AS runner

LABEL org.opencontainers.image.source="https://github.com/dyedd/lens"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LENS_DATABASE_URL=sqlite+aiosqlite:////app/data/data.db
ENV PATH=/app/.venv/bin:$PATH

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY lens_api ./lens_api
COPY migrations ./migrations
COPY scripts/docker/app-entrypoint.sh /usr/local/bin/app-entrypoint
COPY --from=ui-builder /app/ui/out /app/ui

RUN --mount=type=bind,from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --link-mode=copy \
    && chmod +x /usr/local/bin/app-entrypoint \
    && mkdir -p /app/data

EXPOSE 3000

ENTRYPOINT ["app-entrypoint"]
