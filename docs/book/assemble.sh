#!/bin/sh
# Assemble manuscript.md from docs/book/parts/*.md, in lexical order.
# The parts are the source of truth; manuscript.md is a build artifact
# (kept in git so diffs stay reviewable and the repo builds without hooks).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="$DIR/manuscript.md"
: > "$OUT.tmp"
for part in "$DIR"/parts/*.md; do
  cat "$part" >> "$OUT.tmp"
  # A blank line between parts: a part ending in `---` must not butt directly
  # against the next part's heading, or pandoc reads it as a YAML block opener.
  printf '\n' >> "$OUT.tmp"
done
mv "$OUT.tmp" "$OUT"
echo "assembled $(ls "$DIR"/parts/*.md | wc -l | tr -d ' ') parts -> $OUT"
