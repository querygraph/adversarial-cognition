#!/bin/sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
[ -d "$DIR/node_modules" ] || (cd "$DIR" && npm install --silent >/dev/null 2>&1)
exec node "$DIR/ucan_adapter.mjs"
