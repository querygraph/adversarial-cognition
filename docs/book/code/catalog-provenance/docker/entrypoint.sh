#!/usr/bin/env bash
# Bench container entrypoint: wait for the catalogs, bootstrap Polaris, run the
# comparison, and write the report + RESULTS to /bench/out.
set -uo pipefail
cd /bench
mkdir -p out

wait_for() {
  local name="$1" url="$2"
  echo "[entrypoint] waiting for $name" >&2
  for _ in $(seq 1 90); do
    curl -fsS -o /dev/null --max-time 2 "$url" 2>/dev/null && { echo "[entrypoint] $name up" >&2; return 0; }
    sleep 2
  done
  echo "[entrypoint] $name did not come up (will report unavailable)" >&2
}

wait_for minio "http://minio:9000/minio/health/live"
wait_for nessie "http://nessie:19120/iceberg/v1/config"
wait_for gravitino "http://gravitino:9001/iceberg/v1/config"

export CATALOG_PROVENANCE_NESSIE_CMD=/bench/adapters/nessie/run.sh
export CATALOG_PROVENANCE_GRAVITINO_CMD=/bench/adapters/gravitino/run.sh

# --- Polaris OAuth bootstrap (token + S3 catalog) ---------------------------
POLARIS_BASE="http://polaris:8181"
get_polaris_token() {
  curl -sf -X POST "$POLARIS_BASE/api/catalog/v1/oauth/tokens" \
    -d "grant_type=client_credentials&client_id=root&client_secret=secret&scope=PRINCIPAL_ROLE:ALL" \
    2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])" 2>/dev/null
}
echo "[entrypoint] waiting for polaris" >&2
token=""
for _ in $(seq 1 60); do
  token=$(get_polaris_token || true)
  [ -n "$token" ] && break
  sleep 2
done
if true; then
  if [ -n "${token:-}" ]; then
    curl -s -o /dev/null -X POST "$POLARIS_BASE/api/management/v1/catalogs" \
      -H "Authorization: Bearer $token" -H 'content-type: application/json' \
      -d '{"catalog":{"name":"bench","type":"INTERNAL","properties":{"default-base-location":"s3://warehouse/bench"},"storageConfigInfo":{"storageType":"S3","allowedLocations":["s3://warehouse/bench"],"endpoint":"http://minio:9000","stsUnavailable":true,"pathStyleAccess":true}}}' 2>/dev/null || true
    # Grant the catalog's content-management role to the principal role so the
    # principal can actually create/write tables (Polaris RBAC).
    curl -s -o /dev/null -X PUT "$POLARIS_BASE/api/management/v1/catalogs/bench/catalog-roles/catalog_admin/grants" \
      -H "Authorization: Bearer $token" -H 'content-type: application/json' \
      -d '{"grant":{"type":"catalog","privilege":"CATALOG_MANAGE_CONTENT"}}' 2>/dev/null || true
    curl -s -o /dev/null -X PUT "$POLARIS_BASE/api/management/v1/principal-roles/service_admin/catalog-roles/bench" \
      -H "Authorization: Bearer $token" -H 'content-type: application/json' \
      -d '{"catalogRole":{"name":"catalog_admin"}}' 2>/dev/null || true
    export POLARIS_TOKEN="$token"
    export POLARIS_URI="$POLARIS_BASE/api/catalog"
    export POLARIS_WAREHOUSE="bench"
    export CATALOG_PROVENANCE_POLARIS_CMD=/bench/adapters/polaris/run.sh
    echo "[entrypoint] polaris bootstrapped" >&2
  else
    echo "[entrypoint] polaris token bootstrap failed; reporting unavailable" >&2
  fi
fi

# LakeCat participates through the reference model in this stack.
report=out/catalog-provenance-v1.json
python3 run_benchmark.py --catalogs "${1:-all}" --json "$report"
code=$?
python3 render_results.py "$report" out/RESULTS.md 2>/dev/null || true
echo "[entrypoint] wrote $report and out/RESULTS.md" >&2
exit "$code"
