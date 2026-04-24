FROM node:22-bookworm-slim AS ui-deps

WORKDIR /app/ui

RUN corepack enable

COPY ui/package.json ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:22-bookworm-slim AS ui-builder

WORKDIR /app/ui

RUN corepack enable

COPY --from=ui-deps /app/ui/node_modules ./node_modules
COPY ui ./

ARG LENS_UI_BACKEND_BASE_URL=http://127.0.0.1:18080
ENV NODE_ENV=production \
    LENS_UI_BACKEND_BASE_URL=${LENS_UI_BACKEND_BASE_URL}

RUN pnpm build

FROM python:3.11-slim-bookworm AS runner

LABEL org.opencontainers.image.source="https://github.com/dyedd/lens"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    LENS_HOST=0.0.0.0 \
    LENS_PORT=18080 \
    TZ=Asia/Shanghai

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
       bash ca-certificates curl tini tzdata \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install --yes --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY lens_api ./lens_api
COPY migrations ./migrations
COPY scripts/docker/app-entrypoint.sh /usr/local/bin/app-entrypoint

RUN pip install --upgrade pip \
    && pip install . \
    && chmod +x /usr/local/bin/app-entrypoint \
    && mkdir -p /app/data

COPY --from=ui-builder /app/ui/.next/standalone /app/ui
COPY --from=ui-builder /app/ui/.next/static /app/ui/.next/static
COPY --from=ui-builder /app/ui/public /app/ui/public

EXPOSE 3000 18080

ENTRYPOINT ["tini", "--", "app-entrypoint"]
