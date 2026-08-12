#!/bin/sh
# cognee is pinned to the release the adapter's API surface (search routing,
# temporal_cognify, permission methods) and the published run were verified
# against; litellm is pinned to the last pure-python wheel: newer releases
# require a Rust/maturin build that fails without a toolchain.
exec uv run --python 3.12 --with 'cognee==1.4.1' --with 'litellm==1.91.4' -- python3 "$(dirname "$0")/adapter.py"
