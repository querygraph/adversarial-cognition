"""CLI entry: run one agent-memory backend under the shared harness.

Usage: ``python3 -m agent_harness.run_backend <backend>`` with the benchmark
request on stdin — the same adapter command contract every v1 adapter uses,
so the backend plugs into EXTERNAL_SYSTEMS via an env command variable.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_harness.driver import run
from agent_harness.ollama import transport


def make_backend(name: str):
    if name == "marciana-agent":
        from adapters.agent_backends.marciana_agent import MarcianaAgentBackend

        return MarcianaAgentBackend()
    if name == "memfs-agent":
        from adapters.agent_backends.memfs_agent import MemFSAgentBackend

        return MemFSAgentBackend()
    if name == "letta-agent":
        from adapters.agent_backends.letta_agent import LettaAgentBackend

        return LettaAgentBackend()
    raise SystemExit(f"unknown agent backend: {name}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_backend.py <backend>")
    run(make_backend(sys.argv[1]), transport)


if __name__ == "__main__":
    main()
