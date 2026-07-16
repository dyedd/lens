#!/bin/sh
set -eu

umask 077

RAW_BASE_URL="https://raw.githubusercontent.com/dyedd/lens/main"

download_file() (
    url="$1"
    destination="$2"
    temp_file="$(mktemp "./.$(basename "$destination").tmp.XXXXXX")"
    trap 'rm -f "$temp_file"' 0 HUP INT TERM

    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$url" -o "$temp_file"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$url" -O "$temp_file"
    else
        echo "curl or wget is required" >&2
        exit 1
    fi

    chmod 644 "$temp_file"
    mv "$temp_file" "$destination"
)

if [ ! -f docker-compose.yml ]; then
    download_file "$RAW_BASE_URL/docker-compose.yml" docker-compose.yml
fi

if [ ! -f .env.example ]; then
    download_file "$RAW_BASE_URL/.env.example" .env.example
fi

if [ ! -f .env ]; then
    if ! command -v openssl >/dev/null 2>&1; then
        echo "openssl is required" >&2
        exit 1
    fi

    secret_key="$(openssl rand -hex 32)"
    temp_env="$(mktemp ./.env.tmp.XXXXXX)"
    trap 'rm -f "$temp_env"' 0 HUP INT TERM
    sed "s/^LENS_AUTH_SECRET_KEY=.*/LENS_AUTH_SECRET_KEY=$secret_key/" \
        .env.example >"$temp_env"

    if ! grep -q "^LENS_AUTH_SECRET_KEY=$secret_key$" "$temp_env"; then
        echo "LENS_AUTH_SECRET_KEY is missing from .env.example" >&2
        exit 1
    fi

    mv "$temp_env" .env
    trap - 0 HUP INT TERM
fi

secret_key_lines="$(grep -Ec '^LENS_AUTH_SECRET_KEY=[0-9a-f]{64}$' .env || true)"
secret_key_assignments="$(grep -Ec '^LENS_AUTH_SECRET_KEY=' .env || true)"
if [ "$secret_key_lines" -ne 1 ] || [ "$secret_key_assignments" -ne 1 ]; then
    echo "LENS_AUTH_SECRET_KEY in .env must be a 64-character hexadecimal value" >&2
    exit 1
fi

chmod 600 .env
mkdir -p data

echo "Deployment files are ready."
echo "Run: docker compose pull && docker compose up -d"
