# syntax=docker/dockerfile:1

ARG NODE_IMAGE=node:22-bookworm-slim
ARG PNPM_VERSION=10.17.1
ARG UV_VERSION=0.11.28

FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS ui-base

WORKDIR /app/frontend

ARG PNPM_VERSION
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH

RUN corepack enable pnpm \
    && corepack prepare pnpm@${PNPM_VERSION} --activate

FROM ui-base AS ui-deps

COPY frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm fetch

COPY frontend/package.json ./
RUN pnpm install --frozen-lockfile --offline

FROM ui-base AS ui-builder

COPY --from=ui-deps /app/frontend/node_modules ./node_modules
COPY frontend ./

ENV NODE_ENV=production

RUN pnpm build

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:3.14-slim AS runner

LABEL org.opencontainers.image.source="https://github.com/dyedd/lens"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LENS_DATABASE_URL=sqlite+aiosqlite:////app/data/data.db
ENV PATH=/app/.venv/bin:$PATH

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml ./backend/
RUN --mount=type=bind,from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-workspace --package app --link-mode=copy \
    && mkdir -p /app/data

# Installed editable on purpose: `app.cli` resolves `alembic.ini` and the Alembic
# script directory relative to the package, so the source tree must stay in place.
COPY backend/alembic.ini ./backend/
COPY backend/app ./backend/app
RUN --mount=type=bind,from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package app --link-mode=copy

COPY --chmod=755 scripts/docker/app-entrypoint.sh /usr/local/bin/app-entrypoint
# vite.config.ts writes the build into the Python package, so the path mirrors
# the repository layout: /app/frontend/../backend/app/frontend.
COPY --from=ui-builder /app/backend/app/frontend /app/backend/app/frontend

EXPOSE 3000

ENTRYPOINT ["app-entrypoint"]
