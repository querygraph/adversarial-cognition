#!/bin/sh
# Fetches the opa binary on first run, then evaluates the Rego policy per case.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
OPA="$DIR/bin/opa"
if [ ! -x "$OPA" ]; then
  mkdir -p "$DIR/bin"
  case "$(uname -s)-$(uname -m)" in
    Darwin-arm64)  A=darwin_arm64_static ;;
    Darwin-x86_64) A=darwin_amd64 ;;
    Linux-aarch64) A=linux_arm64_static ;;
    *)             A=linux_amd64_static ;;
  esac
  curl -sSL -o "$OPA" "https://openpolicyagent.org/downloads/latest/opa_${A}"
  chmod +x "$OPA"
fi
exec python3 "$DIR/opa_adapter.py"
