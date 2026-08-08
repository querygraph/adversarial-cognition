#!/bin/sh
# Akka + Fluree adapter: stdlib-only Python over the Fluree HTTP API.
exec /usr/bin/env python3 "$(dirname "$0")/adapter.py"
