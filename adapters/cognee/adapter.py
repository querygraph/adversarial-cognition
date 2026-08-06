"""Cognee adapter for MARCIANA-ADVERSARIAL-v1.

Cognee builds a knowledge graph and vector index from added text ("cognify")
and answers via search. It offers per-dataset partitioning and deletion but
no authorization, provenance, replay, idempotency, or temporal as-of query.
This adapter claims retrieval, isolation, clearance (all via cognee's native
dataset scoping: an org-shared tier, an org-private tier, and per-principal
own-* datasets), and persistence, and declares the rest unsupported. It
never simulates a missing boundary. Abstention is not claimed: CHUNKS
search returns nearest neighbors with no native relevance threshold.

Note: Marciana takes no Cognee dependency and Cognee is inspiration only in
Marciana; this adapter lives here, in the benchmark repository, and imports
Cognee only in its own isolated environment.

Local-only: configured against Ollama for LLM and embeddings.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol import MemorySystem, Unsupported, run

DATA_ROOT = Path(__file__).resolve().parent / "data"


def _configure() -> None:
    # llama3.1 fails cognify's structured summarization schema (verified);
    # gpt-oss:20b returns clean structured output. Cognee's Ollama embedding
    # engine speaks /api/embed — not the OpenAI-compatible /v1 — and needs
    # explicit dimensions plus a HuggingFace tokenizer name, otherwise the
    # embedding connection test fails before any pipeline runs.
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
    os.environ.setdefault("CACHING", "false")
    os.environ.setdefault("LLM_PROVIDER", "ollama")
    os.environ.setdefault("LLM_MODEL", os.environ.get("MARCIANA_OLLAMA_MODEL", "gpt-oss:20b"))
    os.environ.setdefault("LLM_ENDPOINT", os.environ.get("MARCIANA_OLLAMA_URL",
                                                          "http://localhost:11434/v1"))
    os.environ.setdefault("LLM_API_KEY", "ollama")
    os.environ.setdefault("EMBEDDING_PROVIDER", "ollama")
    os.environ.setdefault("EMBEDDING_MODEL", "nomic-embed-text")
    os.environ.setdefault("EMBEDDING_ENDPOINT", "http://localhost:11434/api/embed")
    os.environ.setdefault("EMBEDDING_DIMENSIONS", "768")
    os.environ.setdefault("HUGGINGFACE_TOKENIZER", "nomic-ai/nomic-embed-text-v1.5")
    import cognee

    cognee.config.system_root_directory(str(DATA_ROOT / "system"))
    cognee.config.data_root_directory(str(DATA_ROOT / "data"))


class CogneeSystem(MemorySystem):
    name = "cognee"
    version = "oss"
    # No scoped single-memory forget with derived cascade, so "forget" and
    # "derived-tracking" are not claimed and forget-derived is unsupported.
    capabilities = frozenset({"retrieval", "isolation", "clearance",
                              "persistence"})

    def __init__(self) -> None:
        _configure()
        self.loop = asyncio.new_event_loop()
        self.dirty: set[str] = set()

    def _dataset(self, principal: str, private: bool) -> str:
        # Sensitivity tiers and tenancy both map onto cognee datasets: the
        # shared organization tier, the private tier, and per-principal spaces.
        if private:
            return "org-private"
        return "org-shared" if principal == "operator" else f"own-{principal}"

    def _scope(self, principal: str) -> tuple[str, ...]:
        return {
            "operator": ("org-shared", "org-private", "own-operator"),
            "analyst": ("org-shared", "own-analyst"),
            "outsider": ("own-outsider",),
        }.get(principal, ())

    def reset(self) -> None:
        import cognee

        try:
            self.loop.run_until_complete(cognee.prune.prune_data())
            self.loop.run_until_complete(cognee.prune.prune_system(metadata=True))
        except Exception:
            pass  # a pristine store has nothing to prune
        self.dirty = set()

    def remember(self, memory_id, text, principal, valid_from=None,
                 valid_until=None, private=False, nonce=None, supersedes=None,
                 derived_from=()) -> bool:
        if nonce is not None:
            raise Unsupported("nonce replay protection")
        import cognee

        dataset = self._dataset(principal, private)
        tagged = f"[{memory_id}] {text}"
        self.loop.run_until_complete(cognee.add(tagged, dataset_name=dataset))
        # cognify lazily at recall so one pipeline run covers a case's seeds.
        self.dirty.add(dataset)
        return True

    def recall(self, query, principal, as_of=None):
        if as_of is not None:
            raise Unsupported("temporal as-of query")
        import cognee
        from cognee import SearchType
        from cognee.modules.data.exceptions import DatasetNotFoundError

        scope = self._scope(principal)
        if not scope:
            raise Unsupported(f"principal {principal}")
        try:
            pending = [dataset for dataset in scope if dataset in self.dirty]
            if pending:
                self.loop.run_until_complete(cognee.cognify(datasets=pending))
                self.dirty -= set(pending)
            results = self.loop.run_until_complete(cognee.search(
                query_text=query, query_type=SearchType.CHUNKS,
                datasets=list(scope), top_k=15))
        except DatasetNotFoundError:
            # A principal with no datasets gets a 404 from cognee —
            # non-disclosure, not an adapter error.
            return ()
        found, seen = [], set()
        for item in results:
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            for memory_id in ("price-current", "price-old", "soil",
                              "private-farm", "prompt-injection"):
                if f"[{memory_id}]" in text and memory_id not in seen:
                    seen.add(memory_id)
                    found.append(memory_id)
        return tuple(found)

    def restart(self) -> None:
        import cognee

        self.loop.run_until_complete(cognee.disconnect())


def main() -> None:
    system = CogneeSystem()
    # cognee logs on stdout; buffer the driver's output and re-emit only the
    # outcome payload so the runner sees clean JSON.
    buffer = io.StringIO()
    sys.stdout = buffer
    try:
        run(system)
    finally:
        sys.stdout = sys.__stdout__
    for line in reversed(buffer.getvalue().splitlines()):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "cases" in parsed:
            print(line)
            return
    raise SystemExit("adapter produced no outcome payload")


if __name__ == "__main__":
    main()
