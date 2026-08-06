"""Letta adapter for MARCIANA-ADVERSARIAL-v1.

Letta (formerly MemGPT) is a stateful-agent memory server. This adapter uses
its archival-memory path directly — archives and passages with Ollama
embeddings, no LLM agent loop — so results are as deterministic as the
embedder. One archive per principal is Letta's own scoping boundary:
``operator`` (who alone holds the private memory), ``analyst``,
``outsider``, and ``advertiser`` each search only their archive.

Temporal mapping (documented limitation): a memory's ``valid_from`` becomes
the passage ``created_at`` and an as-of recall becomes a search
``end_date``. Letta can express "not yet valid" but has no validity-end
concept, so a superseded fact stays searchable at later as-of dates; the
``retrieval-current`` case therefore genuinely tests whether ranking still
prefers the current fact with both present. Letta has no clearance/purpose
authorization, no provenance-digest binding, no nonce/idempotency ledger,
and no supersession; those capabilities are unclaimed and declared
unsupported.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol import MemorySystem, run

from letta_client import Letta

LETTA_URL = os.environ.get("MARCIANA_LETTA_URL", "http://localhost:8285")
# Explicit OpenAI-compatible embedding config: letta 0.16's ollama handle
# resolution points the OpenAI client at the raw Ollama base URL (no /v1),
# which 404s, so the adapter supplies the correct endpoint itself.
EMBEDDING_CONFIG = {
    "embedding_endpoint_type": "openai",
    "embedding_endpoint": os.environ.get(
        "MARCIANA_LETTA_EMBED_URL", "http://host.docker.internal:11434/v1"
    ),
    "embedding_model": os.environ.get(
        "MARCIANA_LETTA_EMBED_MODEL", "nomic-embed-text:latest"
    ),
    "embedding_dim": 768,
}
MARKER = re.compile(r"\[id:([A-Za-z0-9_.:-]+)\]")
# Deterministic stamp for memories without an explicit validity start, chosen
# inside the corpus's active window so as-of filtering never hides them.
DEFAULT_CREATED = date(2026, 1, 15)
SEARCH_LIMIT = 8


def _stamp(value: date) -> str:
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc).isoformat()


class LettaSystem(MemorySystem):
    name = "letta"
    version = "unknown"
    capabilities = frozenset(
        {"retrieval", "isolation", "temporal", "forget", "persistence"}
    )

    def __init__(self) -> None:
        self.client = Letta(base_url=LETTA_URL, max_retries=5)
        try:
            info = self.client.health()
            self.version = getattr(info, "version", None) or "unknown"
        except Exception:
            pass
        self.archives: dict[str, str] = {}
        self.passages: dict[tuple[str, str], str] = {}

    def reset(self) -> None:
        # Materialize before deleting: the list is cursor-paginated, and
        # deleting mid-iteration would 404 on a cursor naming a removed id.
        for archive_id in [archive.id for archive in self.client.archives.list()]:
            self.client.archives.delete(archive_id)
        self.archives.clear()
        self.passages.clear()

    def _archive(self, principal: str) -> str:
        if principal not in self.archives:
            archive = self.client.archives.create(
                name=f"adversarial-{principal}", embedding_config=EMBEDDING_CONFIG
            )
            self.archives[principal] = archive.id
        return self.archives[principal]

    def remember(self, memory_id, text, principal, valid_from=None,
                 valid_until=None, private=False, nonce=None, supersedes=None,
                 derived_from=()) -> bool:
        # nonce/supersedes/derived_from and valid_until have no Letta
        # equivalent; the matching capabilities are unclaimed, so the driver
        # never relies on them here. Privacy is archive scoping: the memory
        # lives only in its principal's archive.
        passage = self.client.archives.passages.create(
            self._archive(principal),
            text=f"[id:{memory_id}] {text}",
            created_at=_stamp(valid_from or DEFAULT_CREATED),
            metadata={"bench_id": memory_id},
        )
        self.passages[(principal, memory_id)] = passage.id
        return True

    def recall(self, query, principal, as_of=None):
        kwargs = {"end_date": _stamp(as_of)} if as_of is not None else {}
        results = self.client.passages.search(
            archive_id=self._archive(principal),
            query=query,
            limit=SEARCH_LIMIT,
            **kwargs,
        )
        ids = []
        for item in results:
            match = MARKER.match(item.passage.text or "")
            if match and match.group(1) not in ids:
                ids.append(match.group(1))
        return tuple(ids)

    def forget(self, memory_id, principal) -> bool:
        passage_id = self.passages.pop((principal, memory_id), None)
        if passage_id is None:
            return False
        self.client.archives.passages.delete(
            passage_id, archive_id=self._archive(principal)
        )
        return True

    def restart(self) -> None:
        # Data durability lives in the server's Postgres store; a client
        # restart reconnects and must observe identical state.
        self.client = Letta(base_url=LETTA_URL, max_retries=5)


if __name__ == "__main__":
    run(LettaSystem())
