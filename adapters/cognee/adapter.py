"""Cognee adapter for MARCIANA-ADVERSARIAL-v1.

Cognee builds a knowledge graph and vector index from added text ("cognify")
and answers via search. It has a temporal graph (events carry validity
intervals, queried with ``SearchType.TEMPORAL``) and an enforced
multi-tenant permission layer (users, roles, per-dataset ACLs). It has no
provenance digests, nonce replay protection, idempotency keys, purpose
binding, or user-level derivation tracking, and this adapter declares those
unsupported rather than simulating them.

Claimed: retrieval, temporal, isolation, clearance, persistence.

Note: cognee's ``forget()`` does provide item-level deletion, but the only
forget case in the corpus (``forget-derived``) also requires
``derived-tracking`` — cognee does not cascade deletion to separately
ingested derived documents — so ``forget`` is not claimed and that case
stays unsupported.

Local-only: configured against Ollama for LLM and embeddings.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol import MemorySystem, Unsupported, run

DATA_ROOT = Path(__file__).resolve().parent / "data"

# The memory IDs the corpus can return, tagged into the stored text so the
# benchmark's ranked-ID contract can be read back off cognee's own
# reference list.
CORPUS_IDS = ("price-current", "price-old", "soil", "private-farm",
              "prompt-injection", "summary", "replay-fact", "durable-fact")

PRINCIPALS = ("operator", "analyst", "outsider")

# A single recall is bounded so one non-returning query fails its own case
# rather than stalling the whole run. Override for slower local models.
RECALL_TIMEOUT_SECONDS = float(os.environ.get("MARCIANA_COGNEE_RECALL_TIMEOUT", "180"))
INGEST_TIMEOUT_SECONDS = float(os.environ.get("MARCIANA_COGNEE_INGEST_TIMEOUT", "600"))


def _configure() -> None:
    # llama3.1 fails cognify's structured summarization schema (verified);
    # gpt-oss:20b returns clean structured output. Cognee's Ollama embedding
    # engine speaks /api/embed — not the OpenAI-compatible /v1 — and needs
    # explicit dimensions plus a HuggingFace tokenizer name, otherwise the
    # embedding connection test fails before any pipeline runs.
    #
    # Access control is left ON (cognee's default). Isolation and clearance
    # are then enforced by cognee's permission layer rather than by the
    # adapter choosing which datasets to read.
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "true")
    os.environ.setdefault("CACHING", "false")
    _ollama = os.environ.get("MARCIANA_OLLAMA_URL", "http://localhost:11434").rstrip("/").removesuffix("/v1")
    os.environ.setdefault("LLM_PROVIDER", "ollama")
    os.environ.setdefault("LLM_MODEL", os.environ.get("MARCIANA_OLLAMA_MODEL", "gpt-oss:20b"))
    os.environ.setdefault("LLM_ENDPOINT", f"{_ollama}/v1")
    os.environ.setdefault("LLM_API_KEY", "ollama")
    os.environ.setdefault("EMBEDDING_PROVIDER", "ollama")
    os.environ.setdefault("EMBEDDING_MODEL", "nomic-embed-text")
    os.environ.setdefault("EMBEDDING_ENDPOINT", f"{_ollama}/api/embed")
    os.environ.setdefault("EMBEDDING_DIMENSIONS", "768")
    os.environ.setdefault("HUGGINGFACE_TOKENIZER", "nomic-ai/nomic-embed-text-v1.5")
    import cognee

    cognee.config.system_root_directory(str(DATA_ROOT / "system"))
    cognee.config.data_root_directory(str(DATA_ROOT / "data"))


def _validity_clause(valid_from: date | None, valid_until: date | None) -> str:
    """Express the harness's validity window in the text cognee ingests.

    cognee's temporal graph derives event intervals from the text of what it
    is told, so a validity window is expressed the way cognee consumes it —
    the same translation the Graphiti adapter makes with ``reference_time``
    and the Akka adapter with ``b:validFrom``/``b:validUntil`` triples.
    """
    if valid_from and valid_until:
        return f" (valid from {valid_from.isoformat()} until {valid_until.isoformat()})"
    if valid_from:
        return f" (valid from {valid_from.isoformat()} onward)"
    if valid_until:
        return f" (valid until {valid_until.isoformat()})"
    return ""


class CogneeSystem(MemorySystem):
    name = "cognee"
    version = "oss"
    capabilities = frozenset({"retrieval", "temporal", "isolation", "clearance",
                              "persistence"})

    def __init__(self) -> None:
        _configure()
        self.loop = asyncio.new_event_loop()
        self.users: dict[str, object] = {}
        # Validity windows that have since closed, recorded as they are
        # written. See _is_historical.
        self.closed_windows: list[tuple[date | None, date]] = []

    # -- principals and datasets ------------------------------------------

    def _dataset(self, private: bool) -> str:
        return "org-private" if private else "org-shared"

    async def _user(self, principal: str):
        """Return (creating on first use) the cognee user for a principal."""
        if principal in self.users:
            return self.users[principal]
        from cognee.modules.users.methods import create_user, get_user_by_email

        # A reserved TLD (.test/.example) is rejected by cognee's email
        # validation, so principals get addresses on a normal domain.
        email = f"{principal}@adversarial-cognition.org"
        user = await get_user_by_email(email)
        if user is None:
            user = await create_user(email=email, password="benchmark-only",
                                     is_verified=True)
        self.users[principal] = user
        return user

    async def _grant_shared_read(self) -> None:
        """Operator shares only the org-shared dataset with the analyst.

        The private dataset is never shared, and the outsider is granted
        nothing — so clearance and tenancy are decided by cognee's ACLs,
        not by which dataset name the adapter chooses to read.
        """
        from cognee.modules.data.methods import get_datasets_by_name
        from cognee.modules.users.permissions.methods import (
            authorized_give_permission_on_datasets,
        )

        operator = await self._user("operator")
        analyst = await self._user("analyst")
        shared = await get_datasets_by_name(["org-shared"], operator.id)
        if not shared:
            return
        await authorized_give_permission_on_datasets(
            analyst.id, [dataset.id for dataset in shared], "read", operator.id
        )

    # -- MemorySystem ------------------------------------------------------

    def reset(self) -> None:
        import cognee
        from cognee.infrastructure.databases.relational import create_db_and_tables

        async def _reset():
            try:
                await cognee.prune.prune_data()
                await cognee.prune.prune_system(metadata=True)
            except Exception:
                pass  # a pristine store has nothing to prune
            # prune_system drops the metadata database itself, so the schema
            # is recreated before principals are seeded back into it.
            await create_db_and_tables()

        self.loop.run_until_complete(_reset())
        self.users = {}
        self.closed_windows = []

    def remember(self, memory_id, text, principal, valid_from=None,
                 valid_until=None, private=False, nonce=None, supersedes=None,
                 derived_from=()) -> bool:
        if nonce is not None:
            raise Unsupported("nonce replay protection")
        import cognee

        dataset = self._dataset(private)
        if valid_until is not None:
            self.closed_windows.append((valid_from, valid_until))
        tagged = f"[{memory_id}] {text}{_validity_clause(valid_from, valid_until)}"

        async def _write():
            user = await self._user(principal)
            await cognee.add(tagged, dataset_name=dataset, user=user)
            # Ingestion is completed here, inside remember(), so that graph
            # construction is charged to writes like every other adapter's
            # rather than to the first read. temporal_cognify builds the
            # event graph that SearchType.TEMPORAL queries.
            await cognee.cognify(datasets=[dataset], temporal_cognify=True,
                                 user=user)
            if principal == "operator":
                await self._grant_shared_read()

        # Bounded like recall: a cognify that never returns fails its own
        # case instead of being retried three times without a ceiling.
        self.loop.run_until_complete(
            asyncio.wait_for(_write(), timeout=INGEST_TIMEOUT_SECONDS)
        )
        return True

    def _is_historical(self, as_of: date | None) -> bool:
        """Would this as-of date resolve to something other than head state?

        Only when the date falls inside a validity window that has since
        closed — i.e. some fact was true then and is not true now. Reading
        the current state is not a point-in-time query, and reconstructing
        it as one is both slower and less stable, so head-state reads go
        down the ordinary retrieval path.
        """
        if as_of is None:
            return False
        return any(valid_from is None or valid_from <= as_of < valid_until
                   for valid_from, valid_until in self.closed_windows)

    def recall(self, query, principal, as_of=None):
        import cognee
        from cognee import SearchType

        if principal not in PRINCIPALS:
            raise Unsupported(f"principal {principal}")

        historical = self._is_historical(as_of)
        # cognee's temporal retriever extracts the as-of interval from the
        # query itself, so a point-in-time read expresses it in the query.
        query_text = f"{query} as of {as_of.isoformat()}" if historical else query

        async def _read():
            user = await self._user(principal)
            # No dataset list is passed: cognee resolves the readable set
            # from the caller's permissions, so a principal cannot name a
            # dataset it has no grant on. That is the boundary under test.
            #
            # Bounded so that a query cognee never returns from fails its
            # own case instead of hanging the suite: an empty query routes
            # to the temporal retriever and does not come back.
            if historical:
                call = cognee.search(
                    query_text=query_text,
                    query_type=SearchType.TEMPORAL,
                    top_k=15,
                    include_references=True,
                    user=user,
                )
            else:
                # Head-state reads use chunk retrieval: ranking is the
                # vector order, with no LLM in the path, so the same query
                # ranks the same way twice and paraphrases do not reorder
                # it through a generated answer.
                call = cognee.search(
                    query_text=query_text,
                    query_type=SearchType.CHUNKS,
                    top_k=15,
                    user=user,
                )
            return await asyncio.wait_for(call, timeout=RECALL_TIMEOUT_SECONDS)

        results = self.loop.run_until_complete(_read())
        return self._ranked_ids(results)

    @staticmethod
    def _ranked_ids(results) -> tuple[str, ...]:
        """Read ranked memory IDs off cognee's own evidence references.

        ``include_references=True`` appends the source chunks that produced
        the answer, most relevant first. Only that section is parsed — the
        prose answer above it is ignored — so the ordering is cognee's, not
        a re-ranking by the adapter.
        """
        blob = json.dumps(results, default=str)
        _, marker, evidence = blob.partition("Evidence:")
        section = evidence if marker else blob
        found, seen = [], set()
        for match in re.finditer(r"\[([a-z0-9-]+)\]", section):
            memory_id = match.group(1)
            if memory_id in CORPUS_IDS and memory_id not in seen:
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
