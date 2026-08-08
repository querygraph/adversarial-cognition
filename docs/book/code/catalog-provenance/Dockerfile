# CATALOG-PROVENANCE-v1 benchmark runner.
#
# Bundles the reference core, the report scripts, and the Iceberg REST adapters
# (pyiceberg pre-warmed into the uv cache), and drives every reachable catalog.
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy UV_PYTHON=3.12 PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /bench

# Pre-warm the adapters' pyiceberg dependency set into the image cache.
RUN uv run --with 'pyiceberg[s3fs]==0.11.1' --with pyarrow python -c "pass"

COPY . /bench
RUN chmod +x adapters/*/run.sh docker/entrypoint.sh

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["all"]
