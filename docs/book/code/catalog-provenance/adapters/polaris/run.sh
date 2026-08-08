#!/bin/sh
# Adapter command for CATALOG_PROVENANCE_POLARIS_CMD.
exec uv run --python 3.12 --with 'pyiceberg[s3fs]==0.11.1' --with pyarrow -- \
  python3 "$(dirname "$0")/../rest_adapter.py" polaris
