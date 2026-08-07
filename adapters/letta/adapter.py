"""Current Letta App Server adapter for MARCIANA-ADVERSARIAL-v1.

The dependency-free Python protocol driver delegates Letta operations to a
small Node bridge using the current Agent SDK. Every remember, recall, and
forget request is executed as an agent turn against persistent MemFS memory.
Principal-to-agent selection remains adapter routing, not authorization, so
this adapter deliberately does not claim isolation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol import MemorySystem, run


class LettaSystem(MemorySystem):
    name = "letta-app-server"
    version = "agent-sdk-0.6.2/app-server"
    capabilities = frozenset({"retrieval", "temporal", "forget", "persistence"})
    # Memory is reached through an agent turn, not a direct store call. The
    # direct-memory mode overrides this to "direct-api" in __init__.
    interface = "agent-loop"

    def __init__(self) -> None:
        # LETTA_ADAPTER_MODE selects how memory is reached. Default is the
        # agent loop (what Letta ships as its interface). "direct-memory"
        # drives the passage store directly, so the cost of the agent loop can
        # be read as the delta between the two rows. Principal->archive routing
        # is not a Letta authorization boundary (see PR #1), so direct mode
        # claims only the primitives the store itself provides — never
        # isolation — and the adapter still enforces no gate.
        self.mode = os.environ.get("LETTA_ADAPTER_MODE", "agent-loop")
        if self.mode == "direct-memory":
            self.name = "letta-direct-memory"
            self.interface = "direct-api"
            self.capabilities = frozenset({"retrieval", "persistence"})
        self.bridge = subprocess.Popen(
            ["node", str(Path(__file__).with_name("bridge.js"))],
            env={**os.environ, "LETTA_ADAPTER_MODE": self.mode},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.version = str(self._request("info")["version"])

    def _request(self, operation: str, **values):
        if self.bridge.stdin is None or self.bridge.stdout is None:
            raise RuntimeError("Letta bridge has no pipes")
        self.bridge.stdin.write(json.dumps({"op": operation, **values}) + "\n")
        self.bridge.stdin.flush()
        line = self.bridge.stdout.readline()
        if not line:
            raise RuntimeError("Letta bridge exited")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response

    def reset(self) -> None:
        self._request("reset")

    def remember(self, memory_id, text, principal, valid_from=None,
                 valid_until=None, private=False, nonce=None, supersedes=None,
                 derived_from=()) -> bool:
        response = self._request(
            "remember", memory_id=memory_id, text=text, principal=principal,
            valid_from=valid_from.isoformat() if valid_from else None,
            valid_until=valid_until.isoformat() if valid_until else None,
        )
        return bool(response["ok"])

    def recall(self, query, principal, as_of: date | None = None):
        response = self._request(
            "recall", query=query, principal=principal,
            as_of=as_of.isoformat() if as_of else None,
        )
        return tuple(response["ids"])

    def forget(self, memory_id, principal) -> bool:
        return bool(self._request(
            "forget", memory_id=memory_id, principal=principal
        )["ok"])

    def restart(self) -> None:
        self._request("restart")

    def close(self) -> None:
        try:
            if self.bridge.poll() is None:
                self._request("reset")
        except (BrokenPipeError, RuntimeError):
            pass
        finally:
            if self.bridge.poll() is None:
                self.bridge.terminate()
                self.bridge.wait(timeout=10)


if __name__ == "__main__":
    system = LettaSystem()
    try:
        run(system)
    finally:
        system.close()
