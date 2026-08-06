#!/usr/bin/env bash
# Run MARCIANA-ADVERSARIAL-v1 against every configured OSS system adapter.
#
# Adapters run entirely locally: LLM/embeddings via Ollama, infrastructure via
# `docker compose up -d` (Neo4j for Graphiti, Fluree for the Akka adapter).
# Each adapter's run.sh is wired to its command variable below; unconfigured
# systems are reported `unavailable`, never skipped or substituted.
set -euo pipefail

cd "$(dirname "$0")"
here="$PWD"

export MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS="${MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS:-3600}"
[ -x adapters/mem0/run.sh ] && export MARCIANA_ADVERSARIAL_MEM0_CMD="$here/adapters/mem0/run.sh"
[ -x adapters/graphiti/run.sh ] && export MARCIANA_ADVERSARIAL_GRAPHITI_CMD="$here/adapters/graphiti/run.sh"
[ -x adapters/cognee/run.sh ] && export MARCIANA_ADVERSARIAL_COGNEE_CMD="$here/adapters/cognee/run.sh"
[ -x adapters/letta/run.sh ] && export MARCIANA_ADVERSARIAL_LETTA_CMD="$here/adapters/letta/run.sh"
[ -x adapters/akka_fluree/run.sh ] && export MARCIANA_ADVERSARIAL_AKKA_FLUREE_CMD="$here/adapters/akka_fluree/run.sh"

python3 run_benchmark.py \
  --systems all \
  --model reference-smoke-v1 \
  --provider local \
  --profile adversarial-v1-comparative \
  --json reports/marciana-adversarial-v1-comparative.json \
  "$@"
