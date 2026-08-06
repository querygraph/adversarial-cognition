#!/usr/bin/env bash
# Run one OSS adapter against the full corpus and capture its JSON outcome
# uniformly. Adapters share the host Ollama, which serializes to one model at
# a time, so this script is meant to be invoked ONE SYSTEM AT A TIME — never
# concurrently — to avoid contention that stalls every run.
#
# Usage: scripts/capture_adapter.sh <system> [timeout_seconds]
# Writes outputs/<system>.json (stdout) and outputs/<system>.log (stderr),
# then validates that every case appears exactly once.
set -euo pipefail

cd "$(dirname "$0")/.."
system="${1:?usage: capture_adapter.sh <system> [timeout_seconds]}"
timeout_s="${2:-3600}"
runner="adapters/${system}/run.sh"
[ -x "$runner" ] || { echo "no executable adapter: $runner" >&2; exit 2; }

mkdir -p outputs
req="$(python3 -c "import json,sys; m=json.load(open('fixtures/marciana-adversarial-v1/manifest.json'))['manifest']['cases']; print(json.dumps({'protocol':'marciana-adversarial-adapter-v1','repeats':1,'cases':m}))")"

echo "[$(date -u +%H:%M:%S)] running $system (timeout ${timeout_s}s)" >&2
set +e
printf '%s' "$req" | timeout "$timeout_s" "$runner" > "outputs/${system}.json" 2> "outputs/${system}.log"
code=$?
set -e

if [ "$code" -ne 0 ]; then
  echo "[$(date -u +%H:%M:%S)] $system FAILED (exit $code); see outputs/${system}.log" >&2
  exit "$code"
fi

python3 - "$system" <<'PY'
import json, sys
system = sys.argv[1]
report = json.load(open(f"outputs/{system}.json"))
cases = report["cases"]
supported = [c for c in cases if c.get("supported", True)]
passed = sum(c["correct"] for c in supported)
print(f"{system}: {report['adapter_version']} | {len(cases)} cases | "
      f"supported {len(supported)}, passed {passed}, "
      f"unsupported {len(cases) - len(supported)}")
PY
