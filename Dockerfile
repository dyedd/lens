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

FROM node:22-bookworm-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    LENS_HOST=0.0.0.0 \
    LENS_PORT=18080

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends bash ca-certificates python3 python3-venv tini \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY lens_api ./lens_api
COPY migrations ./migrations
COPY scripts/docker/app-entrypoint.sh /usr/local/bin/app-entrypoint

RUN python3 -m venv /opt/venv \
    && python -m pip install --upgrade pip \
    && python -m pip install . \
    && chmod +x /usr/local/bin/app-entrypoint \
    && groupadd --system app \
    && useradd --system --gid app --create-home --home-dir /home/app app \
    && mkdir -p /app/data /app/ui/.next \
    && chown -R app:app /app /home/app /opt/venv

COPY --from=ui-builder --chown=app:app /app/ui/.next/standalone /app/ui
COPY --from=ui-builder --chown=app:app /app/ui/.next/static /app/ui/.next/static
COPY --from=ui-builder --chown=app:app /app/ui/public /app/ui/public

USER app

EXPOSE 3000 18080

ENTRYPOINT ["tini", "--", "app-entrypoint"]
