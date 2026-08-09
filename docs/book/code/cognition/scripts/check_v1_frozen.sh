#!/usr/bin/env bash
# Release gate: no commit may alter the published v1 artifacts.
#
# The golden tests freeze v1 rendering and the v1 corpus digest functionally;
# this check additionally refuses a working tree or commit range that touches
# the published v1 documents and fixtures at all. Run in CI and before any
# release: ./scripts/check_v1_frozen.sh [<base-ref>]
set -euo pipefail
cd "$(dirname "$0")/.."

frozen=(
  "docs/RESULTS.md"
  "fixtures/marciana-adversarial-v1/manifest.json"
  "fixtures/golden/marciana-adversarial-v1-comparative.json"
)

base="${1:-}"
if [ -n "$base" ]; then
  if ! git diff --quiet "$base" -- "${frozen[@]}"; then
    echo "FROZEN v1 artifacts modified since $base:" >&2
    git diff --name-only "$base" -- "${frozen[@]}" >&2
    exit 1
  fi
else
  if ! git diff --quiet HEAD -- "${frozen[@]}"; then
    echo "FROZEN v1 artifacts modified in the working tree:" >&2
    git diff --name-only HEAD -- "${frozen[@]}" >&2
    exit 1
  fi
fi

python3 -m unittest tests.test_render_golden -q
echo "v1 artifacts frozen: OK"
