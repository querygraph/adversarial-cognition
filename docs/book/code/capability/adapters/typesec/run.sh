#!/bin/sh
# Adapter command for CAPABILITY_ADVERSARIAL_TYPESEC_CMD.
# Builds (once) and runs the live TypeSec adapter over typesec-core.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cargo build --release --manifest-path "$DIR/Cargo.toml" >/dev/null 2>&1
exec "$DIR/target/release/typesec-adapter"
