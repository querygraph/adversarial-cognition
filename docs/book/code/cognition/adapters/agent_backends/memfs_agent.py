"""A flat filesystem-style baseline for the agent-memory track.

One shared store, keyword retrieval, no authentication, no temporal window,
no derived tracking. It declares only what it enforces — retrieval,
abstention, forget, persistence — and declines every authorization case
rather than being credited with a boundary the harness would be supplying.
The track's floor row.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_harness.tools import AgentMemoryBackend, Credential, ToolResult

TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> frozenset[str]:
    return frozenset(TOKEN.findall(text.lower()))


class MemFSAgentBackend(AgentMemoryBackend):
    name = "memfs-agent"
    version = "flat-store-1"
    capabilities = frozenset({"retrieval", "abstention", "forget", "persistence"})
    authorization_mechanism = "none"

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.durable: dict[str, str] = {}

    def reset(self) -> None:
        self.store = {}
        self.durable = {}

    def restart(self) -> None:
        # Persistence: the durable copy survives; volatile state is rebuilt.
        self.store = dict(self.durable)

    def provision(self) -> dict[str, str]:
        return {}

    def open_session(self, credential: Credential) -> object | None:
        # No authentication: every caller shares the one store. The empty
        # provision map plus absent authorization capabilities means every
        # isolation/clearance/purpose case is declined, never faked.
        return credential.name

    def write(self, session, memory_id, text, valid_from=None,
              valid_until=None, private=False, derived_from=()) -> ToolResult:
        if not memory_id:
            return ToolResult(ok=False, error="empty id")
        self.store[memory_id] = text
        self.durable[memory_id] = text
        return ToolResult(ok=True, ids=(memory_id,))

    def read(self, session, query, as_of=None) -> ToolResult:
        wanted = _tokens(query)
        if not wanted:
            return ToolResult(ok=True, results=(), ids=())
        scored = sorted(
            (
                (len(wanted & _tokens(text)), memory_id, text)
                for memory_id, text in self.store.items()
                if wanted & _tokens(text)
            ),
            key=lambda row: (-row[0], row[1]),
        )
        results = tuple(
            {"id": memory_id, "text": text[:200]}
            for _, memory_id, text in scored[:8]
        )
        return ToolResult(ok=True, results=results,
                          ids=tuple(row["id"] for row in results))

    def delete(self, session, memory_id) -> ToolResult:
        if memory_id not in self.store:
            return ToolResult(ok=False, error="not found")
        del self.store[memory_id]
        self.durable.pop(memory_id, None)
        return ToolResult(ok=True, ids=(memory_id,))

    def list_ids(self, session) -> ToolResult:
        return ToolResult(ok=True, ids=tuple(sorted(self.store)))
