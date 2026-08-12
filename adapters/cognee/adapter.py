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

from protocol import MEMORY_IDS, MemorySystem, Unsupported, run

DATA_ROOT = Path(__file__).resolve().parent / "data"

PRINCIPALS = ("operator", "analyst", "outsider")

# A single call is bounded so one non-returning query or cognify fails its
# own case rather than stalling the whole run. The bound cancels at await
# points only — a hang inside synchronous code is not preemptible from the
# event loop — and the driver still retries a timed-out case as transient
# infrastructure, so this is a per-call ceiling, not a per-case one.
# Override for slower local models.
RECALL_TIMEOUT_SECONDS = float(os.environ.get("MARCIANA_COGNEE_RECALL_TIMEOUT", "180"))
INGEST_TIMEOUT_SECONDS = float(os.environ.get("MARCIANA_COGNEE_INGEST_TIMEOUT", "600"))


def _configure() -> None:
    # llama3.1 fails cognify's structured summarization schema (verified);
    # gpt-oss:20b returns clean structured output. Cognee's Ollama embedding
    # engine speaks /api/embed — not the OpenAI-compatible /v1 — and needs
    # explicit dimensions plus a HuggingFace tokenizer name, otherwise the
    # embedding connection test fails before any pipeline runs.
    #
    # Access control is forced ON, not defaulted: cognee's permission layer
    # is the only isolation mechanism this adapter has (no dataset list is
    # passed at read time), so a stale ENABLE_BACKEND_ACCESS_CONTROL=false
    # in the environment must not be allowed to silently void the boundary
    # under test.
    os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "true"
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
        # Validity windows recorded as their writes complete. Adapter-process
        # state only: it survives restart() (which keeps the process alive)
        # but not a process restart, which no harness case exercises. See
        # _is_point_in_time.
        self.windows: list[tuple[date | None, date | None]] = []
        self.shared_granted = False

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
        if self.shared_granted:
            return
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
        self.shared_granted = True

    # -- MemorySystem ------------------------------------------------------

    def reset(self) -> None:
        import cognee
        from cognee.infrastructure.databases.relational import create_db_and_tables

        async def _reset():
            try:
                await cognee.prune.prune_data()
                await cognee.prune.prune_system(metadata=True)
            except Exception as error:
                # A pristine store has nothing to prune, but a locked file or
                # half-written store fails the same way — surface it so a
                # case seeded over surviving data is at least visible in the
                # adapter log rather than silently rescored.
                print(f"cognee prune did not complete: "
                      f"{type(error).__name__}: {error}", file=sys.stderr)
            # prune_system drops the metadata database itself, so the schema
            # is recreated before principals are seeded back into it.
            await create_db_and_tables()

        self.loop.run_until_complete(_reset())
        self.users = {}
        self.windows = []
        self.shared_granted = False

    def remember(self, memory_id, text, principal, valid_from=None,
                 valid_until=None, private=False, nonce=None, supersedes=None,
                 derived_from=()) -> bool:
        if nonce is not None:
            raise Unsupported("nonce replay protection")
        import cognee

        dataset = self._dataset(private)
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

        # Bounded like recall, so a cognify that hangs at an await point
        # fails after a fixed ceiling per attempt (the driver may still
        # retry the case; see the note on the timeout constants above).
        self.loop.run_until_complete(
            asyncio.wait_for(_write(), timeout=INGEST_TIMEOUT_SECONDS)
        )
        # Recorded only after the write completed: a timed-out or failed
        # ingest must not leave a window that routes later reads down the
        # temporal path toward a fact that was never stored.
        if valid_from is not None or valid_until is not None:
            self.windows.append((valid_from, valid_until))
        return True

    def _is_point_in_time(self, as_of: date | None) -> bool:
        """Would this as-of date resolve to something other than head state?

        Head state is only reproduced when every recorded validity window
        contains the date exactly when the window is still open: a closed
        window covering the date means some fact was true then and is not
        now, and a window starting after the date means some fact was not
        yet true then. Reading the current state is not a point-in-time
        query, and reconstructing it as one is both slower and less stable,
        so head-state reads go down the ordinary retrieval path; every other
        date keeps its temporal constraint and is resolved (or honestly
        failed) by cognee's temporal retriever.
        """
        if as_of is None:
            return False
        for valid_from, valid_until in self.windows:
            inside = ((valid_from is None or valid_from <= as_of)
                      and (valid_until is None or as_of < valid_until))
            inside_now = valid_until is None
            if inside != inside_now:
                return True
        return False

    def recall(self, query, principal, as_of=None):
        import cognee
        from cognee import SearchType
        from cognee.modules.data.exceptions import DatasetNotFoundError
        from cognee.modules.retrieval.exceptions.exceptions import NoDataError

        if principal not in PRINCIPALS:
            raise Unsupported(f"principal {principal}")

        point_in_time = self._is_point_in_time(as_of)
        # cognee's temporal retriever extracts the as-of interval from the
        # query itself, so a point-in-time read expresses it in the query.
        query_text = f"{query} as of {as_of.isoformat()}" if point_in_time else query

        async def _read():
            user = await self._user(principal)
            # No dataset list is passed: cognee resolves the readable set
            # from the caller's permissions, so a principal cannot name a
            # dataset it has no grant on. That is the boundary under test.
            #
            # Point-in-time reads take the temporal retriever with the
            # evidence references that produced the answer; head-state
            # reads take chunk retrieval, where ranking is the vector
            # order with no LLM in the path, so the same query ranks the
            # same way twice and paraphrases do not reorder it through a
            # generated answer. Bounded so that a query cognee never
            # returns from (at an await point) fails its own case instead
            # of hanging the suite.
            references = {"include_references": True} if point_in_time else {}
            return await asyncio.wait_for(
                cognee.search(
                    query_text=query_text,
                    query_type=(SearchType.TEMPORAL if point_in_time
                                else SearchType.CHUNKS),
                    top_k=15,
                    user=user,
                    **references,
                ),
                timeout=RECALL_TIMEOUT_SECONDS,
            )

        try:
            results = self.loop.run_until_complete(_read())
        except (DatasetNotFoundError, NoDataError):
            # A principal with no readable datasets gets a 404/no-data error
            # from cognee — non-disclosure, not an adapter error.
            return ()
        return self._ranked_ids(results, point_in_time)

    @staticmethod
    def _chunk_text(item) -> str:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            for key in ("text", "chunk", "content"):
                value = item.get(key)
                if isinstance(value, str):
                    return value
        return json.dumps(item, default=str)

    @classmethod
    def _ranked_ids(cls, results, point_in_time: bool) -> tuple[str, ...]:
        """Read ranked memory IDs off cognee's own ordering.

        Point-in-time responses carry the source chunks that produced the
        answer under an ``Evidence:`` marker, most relevant first; only that
        section is parsed. A response without the marker is an error — the
        prose answer is never a fallback, because ranking IDs by the order
        an LLM happened to mention them would be the adapter re-ranking.

        Chunk responses are already in vector order. Each stored chunk
        begins with its own ``[memory-id]`` tag, and only that leading tag
        is read, so a bracketed ID later inside a memory's text (for
        example, written there by an injected instruction) cannot place
        other IDs into the ranking.
        """
        if point_in_time:
            blob = json.dumps(results, default=str)
            _, marker, evidence = blob.partition("Evidence:")
            if not marker:
                raise RuntimeError(
                    "temporal response carried no Evidence section; "
                    "refusing to rank from the prose answer"
                )
            candidates = (match.group(1) for match in
                          re.finditer(r"\[([a-z0-9-]+)\]", evidence))
        else:
            leading = (re.match(r"\s*\[([a-z0-9-]+)\]", cls._chunk_text(item))
                       for item in (results or ()))
            candidates = (match.group(1) for match in leading if match)
        found, seen = [], set()
        for memory_id in candidates:
            if memory_id in MEMORY_IDS and memory_id not in seen:
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
