#!/usr/bin/env bash
# Adapter command for MARCIANA_ADVERSARIAL_LETTA_CMD.
#
# Letta >= 0.13 requires Postgres — a bare `letta server` from pip cannot
# run against SQLite — so this boots the official letta/letta container
# (server + bundled Postgres), waits for readiness, runs the adapter, and
# removes the container. Stdout carries only the adapter's JSON.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${LETTA_PORT:-8285}"
CONTAINER="adversarial-letta"
IMAGE="${LETTA_IMAGE:-letta/letta:0.16.8}"
mkdir -p data

docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$CONTAINER" \
  -p "$PORT:8283" \
  -e OLLAMA_BASE_URL="http://host.docker.internal:11434" \
  "$IMAGE" >data/boot.log 2>&1
trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true' EXIT

for _ in $(seq 1 180); do
  if curl -sf "http://localhost:$PORT/v1/health/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -sf "http://localhost:$PORT/v1/health/" >/dev/null

MARCIANA_LETTA_URL="http://localhost:$PORT" \
  uv run --python 3.12 --with letta-client==1.12.1 python adapter.py
