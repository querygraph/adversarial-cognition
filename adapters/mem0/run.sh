#!/bin/sh
exec uv run --python 3.12 --with 'mem0ai' --with 'chromadb' --with 'ollama' -- python3 "$(dirname "$0")/adapter.py"
