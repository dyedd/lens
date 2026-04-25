ARG NODE_IMAGE=node:24-bookworm-slim

FROM ${NODE_IMAGE} AS ui-deps

WORKDIR /app/ui

RUN corepack enable

COPY ui/package.json ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM ${NODE_IMAGE} AS ui-builder

WORKDIR /app/ui

RUN corepack enable

COPY --from=ui-deps /app/ui/node_modules ./node_modules
COPY ui ./

ENV NODE_ENV=production \
    LENS_UI_STATIC_EXPORT=1

RUN pnpm build

FROM python:3.14-slim AS runner

LABEL org.opencontainers.image.source="https://github.com/dyedd/lens"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LENS_HOST=0.0.0.0 \
    LENS_PORT=3000 \
    LENS_PROJECT_DIR=/app \
    LENS_UI_STATIC_DIR=/app/ui \
    TZ=Asia/Shanghai

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY lens_api ./lens_api
COPY migrations ./migrations
COPY scripts/docker/app-entrypoint.sh /usr/local/bin/app-entrypoint
COPY --from=ui-builder /app/ui/out /app/ui

RUN python -m pip install . \
    && chmod +x /usr/local/bin/app-entrypoint \
    && mkdir -p /app/data

EXPOSE 3000

ENTRYPOINT ["app-entrypoint"]
