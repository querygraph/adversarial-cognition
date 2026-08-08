FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 make g++ git ca-certificates \
    && npm install --global @letta-ai/letta-code@0.30.8 \
    && rm -rf /var/lib/apt/lists/*

ENV LETTA_LOCAL_BACKEND_DIR=/var/lib/letta
ENV MARCIANA_LETTA_TOKEN=benchmark-local-token
EXPOSE 4500

CMD ["sh", "-c", "printf '%s' \"$MARCIANA_LETTA_TOKEN\" >/tmp/letta-token && letta --backend local connect ollama --base-url \"${MARCIANA_OLLAMA_URL:-http://host.docker.internal:11434}/v1\" && exec letta server --backend local --listen ws://0.0.0.0:4500 --ws-auth capability-token --ws-token-file /tmp/letta-token"]
