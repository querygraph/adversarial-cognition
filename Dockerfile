# MARCIANA-ADVERSARIAL-v1 benchmark runner image.
#
# Bundles the benchmark core, every OSS system adapter, and the report
# scripts. Each adapter resolves its own isolated dependency set through uv, so
# their conflicting requirements stay isolated; those sets are pre-warmed at
# build time so a run needs no network for Python packages. The heavy graph
# and vector services (Fluree, Letta) and the LLM backend (Ollama) are
# sibling containers wired in docker-compose.yml — this image talks to them
# over the network and never spawns a container itself.
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_PYTHON=3.12 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /benchmark

# Pre-warm each adapter's uv dependency set into the image cache. Kept as
# separate layers so a change to one adapter's pins does not rebuild the
# others. `python -c pass` installs the set without importing it (some
# packages probe services on import).
RUN uv run --with 'mem0ai' --with 'chromadb' --with 'ollama' python -c "pass"
RUN uv run --with 'graphiti-core[kuzu]==0.29.3' --with 'openai' python -c "pass"
RUN uv run --with 'cognee' --with 'litellm==1.91.4' python -c "pass"
RUN uv run --with 'letta-client==1.12.1' python -c "pass"

COPY . /benchmark

RUN chmod +x scripts/*.sh adapters/*/run.sh docker/entrypoint.sh

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["all"]
