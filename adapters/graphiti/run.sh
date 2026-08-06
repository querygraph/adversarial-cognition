#!/bin/sh
# Graphiti over embedded Kuzu; LLM+embeddings via local Ollama. No external DB.
exec uv run --python 3.12 --with 'graphiti-core[kuzu]==0.29.3' --with 'openai' -- python3 "$(dirname "$0")/adapter.py"
