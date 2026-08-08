"""The v2 reference backend exposed as the harness memory tool.

The harness-reference row: Marciana's authenticated backend behind the shared
tool contract. Authorization is entirely the system's — ``open_session``
authenticates the harness-held credential against the identity registry, and
every tool call runs under that session's server-side record.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adversarial_cognition.backend import Memory, digest
from adversarial_cognition.backend_v2 import AuthenticatedBackend
from agent_harness.tools import AgentMemoryBackend, Credential, ToolResult


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


class MarcianaAgentBackend(AgentMemoryBackend):
    name = "marciana-agent"
    version = "reference-v2"
    capabilities = frozenset({
        "retrieval", "temporal", "abstention", "isolation", "clearance",
        "purpose", "forget", "derived-tracking", "persistence",
    })
    authorization_mechanism = "typesec-identity-registry/hmac"

    def __init__(self) -> None:
        self.backend = AuthenticatedBackend()
        self._nonce = 0

    def reset(self) -> None:
        # A fresh backend with no seeded memories: the harness performs all
        # seeding through the tool contract, identically for every backend.
        self.backend = AuthenticatedBackend()
        self._nonce = 0

    def restart(self) -> None:
        self.backend.restart()

    def provision(self) -> dict[str, str]:
        return {
            did.split(":")[-1]: credential
            for did, credential in self.backend.credentials.items()
        }

    def open_session(self, credential: Credential) -> object | None:
        did = f"did:key:{credential.name}"
        session = self.backend.authenticate(did, credential.secret)
        if session is None:
            return None
        return (did, credential.secret)

    def _next_nonce(self) -> str:
        self._nonce += 1
        return f"agent-nonce-{self._nonce}"

    def write(self, session, memory_id, text, valid_from=None,
              valid_until=None, private=False, derived_from=()) -> ToolResult:
        if session is None:
            return ToolResult(ok=False, error="no session")
        did, credential = session
        memory = Memory(
            memory_id=memory_id,
            text=text,
            source=f"agent:{did}",
            source_digest=digest(text),
            sensitivity=3 if private else 1,
            valid_from=_parse_date(valid_from) or date(2026, 1, 1),
            valid_until=_parse_date(valid_until),
            derived_from=tuple(derived_from),
        )
        decision = self.backend.remember(memory, did, credential, self._next_nonce())
        return ToolResult(ok=decision.allowed, error=decision.error)

    def read(self, session, query, as_of=None) -> ToolResult:
        if session is None:
            return ToolResult(ok=False, error="no session")
        did, credential = session
        when = _parse_date(as_of) or date(2026, 2, 1)
        decision = self.backend.recall(query, did, credential, when, self._next_nonce())
        if not decision.allowed:
            return ToolResult(ok=False, error=decision.error or "denied")
        results = tuple(
            {"id": memory_id,
             "text": self.backend.core.memories[memory_id].text[:200]}
            for memory_id in decision.ids
            if memory_id in self.backend.core.memories
        )
        return ToolResult(ok=True, results=results, ids=decision.ids)

    def delete(self, session, memory_id) -> ToolResult:
        if session is None:
            return ToolResult(ok=False, error="no session")
        did, credential = session
        decision = self.backend.forget(memory_id, did, credential, self._next_nonce())
        return ToolResult(ok=decision.allowed, ids=decision.ids,
                          error=decision.error)

    def list_ids(self, session) -> ToolResult:
        if session is None:
            return ToolResult(ok=False, error="no session")
        did, credential = session
        decision = self.backend.recall("", did, credential, date(2026, 2, 1),
                                       self._next_nonce())
        return ToolResult(ok=True, ids=decision.ids)
