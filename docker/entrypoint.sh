#!/usr/bin/env bash
# Benchmark container entrypoint: wait for the sibling services, run the
# comparative benchmark, and write the report and RESULTS.md into /benchmark/out.
#
# Argument: the --systems value (default "all"). Examples:
#   docker compose run --rm benchmark              # all systems
#   docker compose run --rm benchmark marciana,akka-fluree
set -euo pipefail
cd /benchmark

systems="${1:-all}"
mkdir -p out

wait_for() {
  local name="$1" url="$2" tries="${3:-180}"
  echo "[entrypoint] waiting for $name at $url" >&2
  for _ in $(seq 1 "$tries"); do
    if curl -s -o /dev/null "$url"; then echo "[entrypoint] $name reachable" >&2; return 0; fi
    sleep 2
  done
  echo "[entrypoint] WARNING: $name never became reachable; it will report as error/unavailable" >&2
}

# Fluree and Letta are the only network services adapters call directly.
wait_for fluree "${MARCIANA_FLUREE_URL%/v1/fluree}" 180
wait_for letta "${MARCIANA_LETTA_URL}/" 240
wait_for ollama "${MARCIANA_OLLAMA_URL}/api/tags" 120

# Wire every adapter command; unset ones are reported unavailable, not skipped.
export MARCIANA_ADVERSARIAL_MEM0_CMD=/benchmark/adapters/mem0/run.sh
export MARCIANA_ADVERSARIAL_GRAPHITI_CMD=/benchmark/adapters/graphiti/run.sh
export MARCIANA_ADVERSARIAL_COGNEE_CMD=/benchmark/adapters/cognee/run.sh
export MARCIANA_ADVERSARIAL_COGNEE_RS_CMD=/benchmark/adapters/cognee_rs/run.sh
export MARCIANA_ADVERSARIAL_LETTA_CMD=/benchmark/adapters/letta/run.sh
export MARCIANA_ADVERSARIAL_AKKA_FLUREE_CMD=/benchmark/adapters/akka_fluree/run.sh

benchmark_version="${MARCIANA_BENCHMARK:-v1}"
if [ "$benchmark_version" = "v2" ]; then
  # v2: the memory-store adapters run under the v2 protocol driver, and the
  # agent-memory backends run under the shared harness. The native-loop letta
  # row is retired (EXTERNAL_SYSTEMS_V2 does not include it).
  export MARCIANA_PROTOCOL_V2=1
  export MARCIANA_HARNESS_MODEL="${MARCIANA_HARNESS_MODEL:-llama3.1:latest}"
  export MARCIANA_ADVERSARIAL_MARCIANA_AGENT_CMD="python3 /benchmark/agent_harness/run_backend.py marciana-agent"
  export MARCIANA_ADVERSARIAL_MEMFS_AGENT_CMD="python3 /benchmark/agent_harness/run_backend.py memfs-agent"
  export MARCIANA_ADVERSARIAL_LETTA_AGENT_CMD="python3 /benchmark/agent_harness/run_backend.py letta-agent"
  export LETTA_BASE_URL="${MARCIANA_LETTA_URL:-http://letta:8283}"
  report=out/marciana-adversarial-v2-comparative.json
  results=out/RESULTS-v2.md
  profile=adversarial-v2-comparative
else
  report=out/marciana-adversarial-v1-comparative.json
  results=out/RESULTS.md
  profile=adversarial-v1-comparative
fi

python3 run_benchmark.py \
  --benchmark "$benchmark_version" \
  --systems "$systems" \
  --model reference-smoke-v1 \
  --provider local-ollama \
  --profile "$profile" \
  --json "$report"

# run_benchmark exits non-zero if a Marciana hard gate trips; the report is
# still written. Render the human-readable results either way.
python3 render_results.py "$report" "$results" || true
echo "[entrypoint] wrote $report and $results" >&2
