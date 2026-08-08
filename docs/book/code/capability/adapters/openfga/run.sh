#!/bin/sh
# Requires an OpenFGA server (OPENFGA_URL, default http://localhost:8085).
exec python3 "$(dirname "$0")/openfga_adapter.py"
