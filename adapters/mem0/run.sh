#!/usr/bin/env bash
# MARCIANA_ADVERSARIAL_MEM0_CMD entry point: JSON request on stdin, one JSON
# outcome payload on stdout. All library noise is kept on stderr.
set -euo pipefail
export MEM0_TELEMETRY=false
cd "$(dirname "$0")/../.."
exec uv run --python 3.12 --quiet \
  --with 'mem0ai==2.0.17' --with 'chromadb>=1.3,<2' --with ollama \
  adapters/mem0/adapter.py
