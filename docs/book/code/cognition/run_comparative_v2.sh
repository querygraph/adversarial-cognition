#!/usr/bin/env bash
# Run MARCIANA-ADVERSARIAL-v2 against every configured system, in two tracks.
#
# Memory-store track: each OSS adapter runs under the v2 protocol driver
# (MARCIANA_PROTOCOL_V2=1), which strips unauthenticated authorization claims
# and probes authenticating systems with a corrupted credential.
# Agent-memory track: backends run under the shared harness
# (agent_harness/run_backend.py) — one model, one loop, one tool contract.
set -euo pipefail

cd "$(dirname "$0")"
here="$PWD"

export MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS="${MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS:-3600}"
export MARCIANA_PROTOCOL_V2=1
export MARCIANA_HARNESS_MODEL="${MARCIANA_HARNESS_MODEL:-llama3.1:latest}"

# Memory-store adapters (the native-loop letta row is retired in v2).
[ -x adapters/mem0/run.sh ] && export MARCIANA_ADVERSARIAL_MEM0_CMD="$here/adapters/mem0/run.sh"
[ -x adapters/graphiti/run.sh ] && export MARCIANA_ADVERSARIAL_GRAPHITI_CMD="$here/adapters/graphiti/run.sh"
[ -x adapters/cognee/run.sh ] && export MARCIANA_ADVERSARIAL_COGNEE_CMD="$here/adapters/cognee/run.sh"
[ -x adapters/cognee_rs/run.sh ] && export MARCIANA_ADVERSARIAL_COGNEE_RS_CMD="$here/adapters/cognee_rs/run.sh"
[ -x adapters/akka_fluree/run.sh ] && export MARCIANA_ADVERSARIAL_AKKA_FLUREE_CMD="$here/adapters/akka_fluree/run.sh"

# Agent-memory backends under the shared harness.
export MARCIANA_ADVERSARIAL_MARCIANA_AGENT_CMD="python3 $here/agent_harness/run_backend.py marciana-agent"
export MARCIANA_ADVERSARIAL_MEMFS_AGENT_CMD="python3 $here/agent_harness/run_backend.py memfs-agent"
export MARCIANA_ADVERSARIAL_LETTA_AGENT_CMD="python3 $here/agent_harness/run_backend.py letta-agent"

python3 run_benchmark.py \
  --benchmark v2 \
  --systems all \
  --model reference-smoke-v1 \
  --provider local \
  --profile adversarial-v2-comparative \
  --json reports/marciana-adversarial-v2-comparative.json \
  "$@"
