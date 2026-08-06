"""Mem0 OSS adapter for MARCIANA-ADVERSARIAL-v1.

Maps the benchmark's behavioral scenarios onto mem0's public OSS API
(mem0ai 2.x): per-principal ``user_id`` scoping for isolation, ``infer=False``
raw storage with a ``bench_id`` metadata key, mem0's own ``threshold``
relevance floor for abstention, and mem0's ``expiration_date`` mechanism for
current-validity temporal filtering. Time-travel (``reference_date``) is
platform-only in OSS, so any historical as-of query raises Unsupported and
is reported as such.
"""

from __future__ import annotations

import contextlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol import AS_OF_NOW, MemorySystem, Unsupported, run

DATA = Path(__file__).resolve().parent / "data"
# Calibrated against nomic-embed-text on this corpus: genuine matches score
# 0.60-0.83 while the unrelated abstention probe peaks at 0.48. The floor is
# enforced by mem0's own search threshold, not by adapter post-filtering.
THRESHOLD = 0.55

def config(epoch: int) -> dict:
    # One store path per case epoch: chromadb caches clients per path, so a
    # deleted-and-recreated directory would collide with the cached handle.
    root = DATA / f"case-{epoch}"
    return {
        "vector_store": {
            "provider": "chroma",
            "config": {"collection_name": "bench", "path": str(root / "chroma")},
        },
        "embedder": {
            "provider": "ollama",
            "config": {"model": "nomic-embed-text", "ollama_base_url": "http://localhost:11434"},
        },
        "llm": {
            "provider": "ollama",
            "config": {"model": "llama3.1", "ollama_base_url": "http://localhost:11434"},
        },
        "history_db_path": str(root / "history.db"),
    }


@contextlib.contextmanager
def quiet():
    """Keep chatty library output away from the protocol's stdout channel."""

    with contextlib.redirect_stdout(sys.stderr):
        yield


class Mem0System(MemorySystem):
    name = "mem0-oss"
    capabilities = frozenset(
        {"retrieval", "isolation", "forget", "persistence", "abstention", "temporal"}
    )

    def __init__(self) -> None:
        import mem0

        self.version = mem0.__version__
        self.memory = None
        self.epoch = 0
        shutil.rmtree(DATA, ignore_errors=True)
        DATA.mkdir(parents=True)

    def _open(self):
        from mem0 import Memory

        with quiet():
            self.memory = Memory.from_config(config(self.epoch))

    def reset(self) -> None:
        if self.memory is not None:
            with quiet():
                self.memory.close()
        self.epoch += 1
        self._open()

    def remember(self, memory_id, text, principal, valid_from=None,
                 valid_until=None, private=False, nonce=None, supersedes=None,
                 derived_from=()) -> bool:
        if nonce is not None or supersedes is not None or derived_from:
            raise Unsupported("mem0 OSS has no nonce, supersession, or derivation API")
        expiration = valid_until.isoformat() if valid_until is not None else None
        with quiet():
            self.memory.add(
                text,
                user_id=principal,
                metadata={"bench_id": memory_id},
                infer=False,
                expiration_date=expiration,
            )
        return True

    def recall(self, query, principal, as_of=None):
        if as_of is not None and as_of != AS_OF_NOW:
            raise Unsupported(
                "mem0 OSS hides expired memories at the current time only; "
                "reference_date time travel is platform-only"
            )
        with quiet():
            found = self.memory.search(
                query, filters={"user_id": principal}, threshold=THRESHOLD
            )
        ids = []
        for row in found.get("results", ()):
            bench_id = (row.get("metadata") or {}).get("bench_id")
            if bench_id and bench_id not in ids:
                ids.append(bench_id)
        return tuple(ids)

    def forget(self, memory_id, principal):
        with quiet():
            rows = self.memory.get_all(filters={"user_id": principal}).get("results", ())
            for row in rows:
                if (row.get("metadata") or {}).get("bench_id") == memory_id:
                    self.memory.delete(row["id"])
                    return True
        return False

    def restart(self) -> None:
        with quiet():
            self.memory.close()
        self._open()


if __name__ == "__main__":
    run(Mem0System())
