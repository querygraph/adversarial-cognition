#!/bin/sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cargo build --release --manifest-path "$DIR/Cargo.toml" >/dev/null 2>&1
exec "$DIR/target/release/biscuit-adapter"
