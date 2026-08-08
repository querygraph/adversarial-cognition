#!/bin/sh
exec uv run --quiet --with pyjwt python3 "$(dirname "$0")/jwt_adapter.py"
