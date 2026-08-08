#!/bin/sh
# Run the full roster: reference + TypeSec + every competitor adapter.
# Library adapters build/fetch their own toolchain on first run; the two ReBAC
# servers (OpenFGA, SpiceDB) come up via docker compose if docker is available.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

export CAPABILITY_ADVERSARIAL_TYPESEC_CMD="$DIR/adapters/typesec/run.sh"
export CAPABILITY_ADVERSARIAL_BISCUIT_CMD="$DIR/adapters/biscuit/run.sh"
export CAPABILITY_ADVERSARIAL_MACAROON_CMD="$DIR/adapters/macaroon-run.sh"
export CAPABILITY_ADVERSARIAL_UCAN_CMD="$DIR/adapters/ucan/run.sh"
export CAPABILITY_ADVERSARIAL_JWT_CMD="$DIR/adapters/jwt-run.sh"
export CAPABILITY_ADVERSARIAL_CEDAR_CMD="$DIR/adapters/cedar/run.sh"
export CAPABILITY_ADVERSARIAL_OPA_CMD="$DIR/adapters/opa/run.sh"

if command -v docker >/dev/null 2>&1; then
  docker compose -f "$DIR/docker-compose.yml" up -d >/dev/null 2>&1 || true
  i=0; while [ $i -lt 30 ]; do curl -sf http://localhost:8085/healthz >/dev/null 2>&1 && break; i=$((i+1)); sleep 1; done
  export OPENFGA_URL="http://localhost:8085"
  export SPICEDB_URL="http://localhost:8446"
  export CAPABILITY_ADVERSARIAL_OPENFGA_CMD="$DIR/adapters/openfga/run.sh"
  export CAPABILITY_ADVERSARIAL_SPICEDB_CMD="$DIR/adapters/spicedb/run.sh"
fi

python3 "$DIR/run_benchmark.py" "$@"
python3 "$DIR/render_results.py" "$DIR/reports/capability-adversarial-v1.json" "$DIR/out/RESULTS.md"
