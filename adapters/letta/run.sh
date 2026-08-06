#!/usr/bin/env bash
# Adapter command for MARCIANA_ADVERSARIAL_LETTA_CMD.
#
# Letta >= 0.13 requires Postgres — a bare `letta server` from pip cannot
# run against SQLite — so this boots the official letta/letta container
# (server + bundled Postgres), waits for readiness, runs the adapter, and
# removes the container. Stdout carries only the adapter's JSON.
set -euo pipefail
cd "$(dirname "$0")"

# Compose mode: the Letta server runs as a sibling service and MARCIANA_LETTA_URL
# already points at it, so connect directly and manage no container here.
if [ -n "${LETTA_EXTERNAL:-}" ]; then
  exec uv run --python 3.12 --with letta-client==1.12.1 python adapter.py
fi

PORT="${LETTA_PORT:-8285}"
CONTAINER="adversarial-letta"
IMAGE="${LETTA_IMAGE:-letta/letta:0.16.8}"
mkdir -p data

docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$CONTAINER" \
  -p "$PORT:8283" \
  -e OLLAMA_BASE_URL="http://host.docker.internal:11434" \
  "$IMAGE" >data/boot.log 2>&1
trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true' EXIT INT TERM

# Health can flip green before the API is steady; require the archives
# endpoint to answer twice, a second apart, before starting the adapter.
ready=0
for _ in $(seq 1 180); do
  if curl -sf "http://localhost:$PORT/v1/archives/" >/dev/null 2>&1; then
    ready=$((ready + 1))
    [ "$ready" -ge 2 ] && break
  else
    ready=0
  fi
  sleep 1
done
curl -sf "http://localhost:$PORT/v1/archives/" >/dev/null

MARCIANA_LETTA_URL="http://localhost:$PORT" \
  uv run --python 3.12 --with letta-client==1.12.1 python adapter.py
