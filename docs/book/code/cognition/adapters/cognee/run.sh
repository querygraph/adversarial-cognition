#!/bin/sh
# litellm is pinned to the last pure-python wheel: newer releases require a
# Rust/maturin build that fails without a toolchain.
exec uv run --python 3.12 --with 'cognee' --with 'litellm==1.91.4' -- python3 "$(dirname "$0")/adapter.py"
