# MARCIANA-ADVERSARIAL-v1 benchmark runner image.
#
# Bundles the benchmark core, every OSS system adapter, and the report
# scripts. Each adapter resolves its own pinned dependency set through uv, so
# their conflicting requirements stay isolated; those sets are pre-warmed at
# build time so a run needs no network for Python packages. The heavy graph
# and vector services (Fluree, Letta) and the LLM backend (Ollama) are
# sibling containers wired in docker-compose.yml — this image talks to them
# over the network and never spawns a container itself.
FROM rust:1.91-bookworm AS cognee-rs-build

ARG COGNEE_RS_COMMIT=038c5a9b0272af4185963b4d198bfb398f7c8ca9
RUN --mount=type=cache,target=/usr/local/cargo/registry,sharing=locked \
    --mount=type=cache,target=/usr/local/cargo/git,sharing=locked \
    --mount=type=cache,target=/cargo-target,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends git build-essential cmake ca-certificates protobuf-compiler libprotobuf-dev \
    && rm -rf /var/lib/apt/lists/* \
    && git clone https://github.com/topoteretes/cognee-rs.git /src/cognee-rs \
    && cd /src/cognee-rs \
    && git checkout "$COGNEE_RS_COMMIT" \
    && sed -i 's#cognee = { path = "../lib", version = "0.2.0" }#cognee = { path = "../lib", version = "0.2.0", default-features = false }#' crates/cli/Cargo.toml \
    && mkdir -p /tmp/protobuf/google/protobuf \
    && cp /usr/include/google/protobuf/*.proto /tmp/protobuf/google/protobuf/ \
    && printf '#!/bin/sh\nexec /usr/bin/protoc -I/tmp/protobuf -I/usr/include "$@"\n' > /usr/local/bin/protoc-wrapper \
    && chmod +x /usr/local/bin/protoc-wrapper \
    && PROTOC=/usr/local/bin/protoc-wrapper \
       CARGO_HOME=/usr/local/cargo \
       CARGO_TARGET_DIR=/cargo-target \
       CARGO_BUILD_JOBS=1 \
       cargo build --release -p cognee-cli --no-default-features --features 'ladybug,sqlite' \
    && cp /cargo-target/release/cognee-cli /tmp/cognee-cli

FROM node:22-bookworm-slim

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/
COPY --from=cognee-rs-build /tmp/cognee-cli /usr/local/bin/cognee-cli

ENV UV_LINK_MODE=copy \
    UV_PYTHON=3.12 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates git python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /benchmark

# Pre-warm each adapter's uv dependency set into the image cache. Kept as
# separate layers so a change to one adapter's pins does not rebuild the
# others. `python -c pass` installs the set without importing it (some
# packages probe services on import).
RUN uv run --with 'mem0ai' --with 'chromadb' --with 'ollama' python -c "pass"
RUN uv run --with 'graphiti-core[kuzu]==0.29.3' --with 'openai' python -c "pass"
RUN uv run --with 'cognee' --with 'litellm==1.91.4' python -c "pass"
COPY adapters/letta/package.json adapters/letta/package-lock.json /benchmark/adapters/letta/
RUN npm ci --ignore-scripts --prefix adapters/letta

COPY . /benchmark

RUN chmod +x scripts/*.sh adapters/*/run.sh docker/entrypoint.sh

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["all"]
