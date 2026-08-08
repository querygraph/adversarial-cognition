#!/usr/bin/env bash
# Vendor clean source snapshots of the four trilogy benchmarks into the book
# repository, so the FirstPair code-profile vault can carry the complete code
# next to the manuscript. Generated build output, caches, VCS metadata, and
# virtual environments are excluded; source, config, fixtures, and docs are kept.
#
# Provenance (source repo + commit) is written to PROVENANCE.md. Re-run after
# updating any benchmark to refresh the snapshot, then commit.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
src="$HOME/src"

# name -> source repository directory
repos=(
  "cognition:$src/adversarial-cognition"
  "catalog-provenance:$src/catalog-provenance"
  "catalog-bench:$src/catalog-bench"
  "capability:$src/adversarial-capability"
)

excludes=(
  --exclude '.git' --exclude '.github'
  --exclude '.venv' --exclude 'venv' --exclude '__pycache__' --exclude '.pytest_cache'
  --exclude '*.pyc' --exclude '.mypy_cache' --exclude '.ruff_cache'
  --exclude 'node_modules' --exclude 'target' --exclude '.linux-target'
  --exclude 'dist' --exclude 'build'
  --exclude 'out' --exclude 'outputs' --exclude '.DS_Store'
  --exclude '*.rlib' --exclude '*.rmeta' --exclude '*.o' --exclude 'incremental'
  --exclude 'lakecat-service'   # 35 MB compiled service binary checked into docker/
  --exclude 'bin/opa'           # 56 MB downloaded OPA tool binary, not source
  --exclude 'data'             # adapter runtime stores (Kuzu/cognee DBs)
  --exclude 'docs'             # prose/assets live in the manuscript, not the code tree
  --exclude '*.db' --exclude '*.sqlite' --exclude '*.parquet'
  --exclude '*.png' --exclude '*.jpg' --exclude '*.jpeg' --exclude '*.gif'
  --exclude '*.pdf' --exclude '*.epub' --exclude '*.mobi'
  --exclude 'docs/book/code'   # never recurse into a vendored snapshot
)

provenance="$here/PROVENANCE.md"
{
  echo "# Vendored benchmark source — provenance"
  echo
  echo "Clean snapshots taken by \`vendor.sh\`. Each tree is the redistributable"
  echo "source of one trilogy benchmark, carried into the FirstPair code vault."
  echo
  echo "| Snapshot | Source repository | Commit |"
  echo "| --- | --- | --- |"
} > "$provenance"

for entry in "${repos[@]}"; do
  name="${entry%%:*}"
  repo="${entry#*:}"
  dest="$here/$name"
  commit="$(git -C "$repo" rev-parse HEAD)"
  echo "vendoring $name from $repo @ ${commit:0:12}"
  rm -rf "$dest"
  mkdir -p "$dest"
  rsync -a "${excludes[@]}" "$repo"/ "$dest"/
  echo "| \`$name\` | $(basename "$repo") | \`$commit\` |" >> "$provenance"
done

echo
echo "Snapshot file counts:"
for entry in "${repos[@]}"; do
  name="${entry%%:*}"
  printf '  %-20s %s files\n' "$name" "$(find "$here/$name" -type f | wc -l | tr -d ' ')"
done
