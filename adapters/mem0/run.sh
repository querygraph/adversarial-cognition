#!/bin/sh
exec uv run --python 3.12 --with 'mem0ai' --with 'chromadb' -- python3 "$(dirname "$0")/adapter.py"
