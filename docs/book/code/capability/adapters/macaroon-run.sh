#!/bin/sh
exec uv run --quiet --with pymacaroons python3 "$(dirname "$0")/macaroon_adapter.py"
