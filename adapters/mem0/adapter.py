"""Mem0 (OSS) adapter for MARCIANA-ADVERSARIAL-v1.

Mem0's open-source library is a retrieval-and-update memory: it adds, searches,
updates, and deletes memories per user, backed by a vector store and an LLM
for fact extraction. It has no tenant/clearance/purpose authorization, no
provenance-digest binding, no nonce/idempotency ledger, and no temporal
as-of query. This adapter therefore claims only the capabilities Mem0
genuinely provides and declares the rest unsupported — it never simulates a
missing security boundary.

Local-only: Mem0 is configured against Ollama (`llama3.1`) and a local
Qdrant-free in-memory store so no data leaves the machine.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol import MemorySystem, Unsupported, run

OLLAMA = os.environ.get("MARCIANA_OLLAMA_URL", "http://localhost:11434")


def _client():
    from mem0 import Memory

    config = {
        "llm": {"provider": "ollama", "config": {
            "model": os.environ.get("MARCIANA_OLLAMA_MODEL", "llama3.1:latest"),
            "ollama_base_url": OLLAMA}},
        "embedder": {"provider": "ollama", "config": {
            "model": "nomic-embed-text:latest", "ollama_base_url": OLLAMA}},
        "vector_store": {"provider": "chroma", "config": {
            "collection_name": "adversarial",
            "path": os.environ.get("MARCIANA_MEM0_PATH", "/tmp/mem0-adversarial")}},
    }
    return Memory.from_config(config)


class Mem0System(MemorySystem):
    name = "mem0"
    version = "oss"
    # Mem0 stores per-user memories and searches them; it does not enforce
    # authorization, provenance, replay, or temporal semantics.
    capabilities = frozenset({"retrieval", "supersession", "abstention",
                              "isolation", "forget", "persistence"})

    def __init__(self) -> None:
        self.memory = _client()
        self._ids: dict[str, str] = {}

    def reset(self) -> None:
        try:
            self.memory.reset()
        except Exception:
            pass
        self._ids = {}

    def _user(self, principal: str) -> str:
        # Mem0's only scoping primitive is user_id. operator/analyst share the
        # organization's store; outsider/advertiser get isolated stores. This
        # models tenant isolation only — not clearance or purpose.
        return "org" if principal in ("operator", "analyst") else principal

    def remember(self, memory_id, text, principal, valid_from=None,
                 valid_until=None, private=False, nonce=None, supersedes=None,
                 derived_from=()) -> bool:
        if nonce is not None:
            raise Unsupported("nonce replay protection")
        result = self.memory.add(text, user_id=self._user(principal),
                                 metadata={"benchmark_id": memory_id})
        entries = result.get("results", result) if isinstance(result, dict) else result
        if entries:
            self._ids[memory_id] = entries[0].get("id", memory_id)
        return True

    def recall(self, query, principal, as_of=None):
        if as_of is not None:
            # Mem0 has no valid-time query; only the current-as-of cases reach
            # here, and those pass as_of=None. A dated query is unsupported.
            raise Unsupported("temporal as-of query")
        if not query.strip():
            return ()
        hits = self.memory.search(query, user_id=self._user(principal), limit=8)
        entries = hits.get("results", hits) if isinstance(hits, dict) else hits
        ordered = []
        for entry in entries:
            benchmark_id = (entry.get("metadata") or {}).get("benchmark_id")
            if benchmark_id:
                ordered.append(benchmark_id)
        return tuple(ordered)

    def forget(self, memory_id, principal):
        store_id = self._ids.get(memory_id)
        if store_id is None:
            return False
        self.memory.delete(store_id)
        return True

    def restart(self) -> None:
        self.memory = _client()


if __name__ == "__main__":
    run(Mem0System())
