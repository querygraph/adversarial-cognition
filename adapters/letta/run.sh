#!/usr/bin/env bash
# Current Letta Agent SDK/App Server adapter command.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d node_modules ]; then
  npm ci --ignore-scripts >/dev/null
fi

# Compose mode supplies a separately managed App Server.
if [ -n "${LETTA_EXTERNAL:-}" ]; then
  exec python3 adapter.py
fi

PORT="${LETTA_PORT:-4505}"
CONTAINER="adversarial-letta-app-server"
IMAGE="${LETTA_IMAGE:-adversarial-letta-app-server}"
docker build -t "$IMAGE" . >/dev/null
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$CONTAINER" \
  -p "$PORT:4500" \
  -e MARCIANA_OLLAMA_URL="${MARCIANA_OLLAMA_URL:-http://host.docker.internal:11434}" \
  -e MARCIANA_LETTA_TOKEN="${MARCIANA_LETTA_TOKEN:-benchmark-local-token}" \
  --add-host host.docker.internal:host-gateway \
  "$IMAGE" >/dev/null
trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true' EXIT INT TERM

for _ in $(seq 1 180); do
  curl -s -o /dev/null "http://localhost:$PORT/" 2>/dev/null && break
  sleep 1
done
curl -s -o /dev/null "http://localhost:$PORT/"

MARCIANA_LETTA_URL="http://localhost:$PORT" \
MARCIANA_LETTA_TOKEN="${MARCIANA_LETTA_TOKEN:-benchmark-local-token}" \
exec python3 adapter.py
