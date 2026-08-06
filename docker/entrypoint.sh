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
wait_for letta "${MARCIANA_LETTA_URL}/v1/health/" 240
wait_for ollama "${MARCIANA_OLLAMA_URL}/api/tags" 120

# Wire every adapter command; unset ones are reported unavailable, not skipped.
export MARCIANA_ADVERSARIAL_MEM0_CMD=/benchmark/adapters/mem0/run.sh
export MARCIANA_ADVERSARIAL_GRAPHITI_CMD=/benchmark/adapters/graphiti/run.sh
export MARCIANA_ADVERSARIAL_COGNEE_CMD=/benchmark/adapters/cognee/run.sh
export MARCIANA_ADVERSARIAL_LETTA_CMD=/benchmark/adapters/letta/run.sh
export MARCIANA_ADVERSARIAL_AKKA_FLUREE_CMD=/benchmark/adapters/akka_fluree/run.sh

report=out/marciana-adversarial-v1-comparative.json
python3 run_benchmark.py \
  --systems "$systems" \
  --model reference-smoke-v1 \
  --provider local-ollama \
  --profile adversarial-v1-comparative \
  --json "$report"

# run_benchmark exits non-zero if a Marciana hard gate trips; the report is
# still written. Render the human-readable results either way.
python3 render_results.py "$report" out/RESULTS.md || true
echo "[entrypoint] wrote $report and out/RESULTS.md" >&2
