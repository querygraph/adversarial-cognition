#!/bin/sh
# Requires a SpiceDB server (SPICEDB_URL default http://localhost:8446, SPICEDB_KEY default capadv).
exec python3 "$(dirname "$0")/spicedb_adapter.py"
