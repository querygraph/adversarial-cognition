#!/bin/sh
# mem0ai pinned to the version the adapter was verified against; later
# releases change search() behavior against the Chroma store.
exec uv run --python 3.12 --with 'mem0ai==2.0.17' --with 'chromadb' --with 'ollama' -- python3 "$(dirname "$0")/adapter.py"
