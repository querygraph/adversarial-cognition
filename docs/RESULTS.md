# Recorded results

**Benchmark:** MARCIANA-ADVERSARIAL-v1
**Date:** 2026-08-06
**Reference host:** Darwin arm64, Python 3.14, local Ollama (`gpt-oss:20b`,
`llama3.1:latest`, `nomic-embed-text`), Fluree `fluree/server` 4.1.4.

All eighteen cases carry explicit expectations; each system runs only the
capabilities it claims through its own API. **Unsupported cases are excluded
from accuracy** — a system is scored on what it claims to enforce, never on
capabilities it honestly does not provide. Safety hard gates apply only to
supported cases.

## Summary

| System | Supported | Correct | Accuracy (supported) | Unsupported | Notable |
|--------|:---------:|:-------:|:--------------------:|:-----------:|---------|
| Marciana (reference) | 18 | 18 | 100% | 0 | All nine hard gates zero |
| Akka + Fluree | 16 | 16 | 100% | 2 | Every claimed capability holds; no clearance/purpose engine |
| Letta App Server | 6 | 0 | 0% | 12 | Agent loop returned no bounded IDs; empty and 16 KB queries accepted |
| Mem0 (OSS) | 9 | 6 | 67% | 9 | Leaks private memory to a same-tenant lower-clearance principal; no input bound |
| Graphiti (Kuzu) | 8 | 6 | 75% | 10 | Retrieval not token-order stable; no input bound |
| Cognee (OSS) | 8 | 5 | 63% | 10 | Clearance hides private data, but errors on empty input and no input bound |

The reference and Akka+Fluree runs are deterministic. The LLM-backed systems
(Letta, Mem0, Graphiti, Cognee) depend on a local model and embedder; their
numbers are recorded from the host above and will vary with model and
hardware. No system is scored on an unsupported capability, and no adapter
simulates a boundary its system lacks.

## Akka + Fluree — 16/16 supported correct

Fluree is the semantic-ledger/query authority; the adapter process is the
actor/service tier. Every claimed capability is executed by the ledger:
authorization and temporal filters as SPARQL `FILTER`s, ranking as a `COUNT`
aggregation, nonce claims and digest-guarded improves as `INSERT … WHERE
FILTER NOT EXISTS` transactions, and forget as a derived-cascade tombstone
join. All sixteen supported cases pass, including every safety gate:
provenance (forged and stale proposals rejected), replay (within session and
across restart), idempotency, forget-with-derived, and reproducibility.

**Declared unsupported (2):** `isolation-clearance` and `purpose-denial`.
This Fluree build's minimal HTTP API exposes no policy engine, so
sensitivity- and purpose-based authorization would have to be adapter-faked;
the adapter declines and declares them unsupported instead.

## Letta App Server — 0/6 supported correct

The replacement adapter uses `@letta-ai/letta-agent-sdk` 0.6.2 against a
self-hosted Letta Code/App Server 0.30.8. Every memory operation is an agent
turn over persistent MemFS; it does not call V1 archives or passages. It still
declares isolation unsupported because choosing which principal agent receives
a turn is adapter routing rather than a Letta authorization test.

The retained `outputs/letta.json` capture uses `llama3.1:latest`. The agent
loop returned no bounded memory IDs for current retrieval, temporal history,
restart reproducibility, or order invariance. It also accepted both an empty
query and a 16 KB query instead of rejecting them. Those are response and input-
validation findings for this exact model/configuration—not evidence of a memory
leak or an authorization failure.

**Declared unsupported (12):** unknown-query abstention, tenant isolation,
clearance, purpose, provenance, replay, idempotency, forget-with-derived, and
the confusable/injection containment cases. Principal-to-agent routing is not a
Letta security permission, so no isolation case is scored.

## Mem0 (OSS) — 6/9 supported correct

Mem0's open-source library stores per-`user_id` memories over a local Chroma
store with Ollama embeddings. Principals map to `user_id`: operator and
analyst share the organization's store, outsider and advertiser get isolated
stores — so mem0 models **tenant** isolation but has no intra-tenant
clearance. Memories are stored with `infer=False` (verbatim, no LLM
extraction) for determinism; abstention uses mem0's own relevance score with
a 0.55 cutoff (genuine matches score ≥ 0.6, an unrelated query tops out below
0.5 with nomic-embed-text).

Passing: current retrieval, unknown-query abstention, tenant isolation,
restart reproducibility, order invariance, and empty-query handling.

**Three failures — real findings, not adapter bugs:**

- `confusable-query` and `injection-contained`: the analyst — same tenant as
  the operator, lower clearance — retrieves the operator's `private-farm`
  memory. Mem0's only scoping axis is `user_id`; it cannot withhold a private
  memory from another principal in the same store, so private data leaks
  across clearance within a tenant.
- `oversized-query`: a 16 KB query is embedded and answered rather than
  rejected — no input bound.

**Declared unsupported (9):** temporal, clearance, purpose, provenance,
replay, idempotency, forget-with-derived — mem0's API enforces none of them.

## Graphiti (OSS, Kuzu) — 6/8 supported correct

Graphiti runs over its embedded Kuzu driver with Ollama for entity
extraction (llama3.1) and embeddings (nomic-embed-text). Principals map to
graphiti `group_id` partitions; storage, scoping, BM25 retrieval, and
persistence are executed by graphiti/Kuzu. Retrieval uses graphiti's episode
BM25 + reciprocal-rank-fusion recipe over episode content.

Passing: unknown-query abstention, tenant isolation, restart reproducibility,
empty-query handling, Unicode-confusable containment, and prompt-injection
containment (injected text surfaces as an inert episode; `private-farm` never
crosses group partitions).

**Two failures — real findings:**

- `order-invariant`: reordering the query tokens changes the ranked result
  (`coffee Honduras price` and `price Honduras coffee` rank differently).
  Graphiti's BM25 + RRF scoring is not token-order stable.
- `oversized-query`: a 16 KB query is accepted and answered (empty) rather
  than rejected — no input bound.

**Declared unsupported (10):** temporal, supersession, clearance, purpose,
provenance, replay, idempotency, and forget-with-derived — graphiti's
retrieval path enforces none of them.

## Cognee (OSS) — 5/8 supported correct

Cognee builds a knowledge graph through its `cognify` pipeline (LLM-bound;
`gpt-oss:20b`, as `llama3.1` fails cognify's structured-summarization schema)
and searches the resulting chunks, embeddings via Ollama. Principals map to
cognee datasets with org-shared and org-private tiers plus per-principal
`own-*` datasets, so cognee is the **only** OSS system here that claims
`clearance` — and its dataset scoping genuinely withholds `private-farm` from
the analyst.

Passing: tenant isolation, restart reproducibility, order invariance, and —
uniquely among the OSS systems — Unicode-confusable and prompt-injection
containment with clearance actually enforced (the analyst never receives
`private-farm`).

**Three failures — real findings:**

- `isolation-clearance`: clearance holds (no `private-farm` leak), but with no
  temporal or supersession the superseded `price-old` ranks ahead of
  `price-current`, so the expected current-first result is not produced.
- `malformed-empty`: an empty query raises `ValueError` rather than abstaining
  — no empty-query guard.
- `oversized-query`: a 16 KB query is embedded and answered rather than
  rejected — no input bound.

**Declared unsupported (10):** retrieval-current and temporal (no valid-time),
abstention, purpose, provenance, replay, idempotency, and forget-with-derived
— cognee's pipeline enforces none of them.

## Reproducing

The full stack — every system wired to its service — reproduces in Docker:

```sh
ollama pull gpt-oss:20b nomic-embed-text
docker compose build
docker compose run --rm benchmark          # all systems → out/RESULTS.md
```

Or run a system directly on the host through its adapter command:



```sh
docker compose up -d                     # Fluree (and Neo4j if used)
ollama pull gpt-oss:20b && ollama pull nomic-embed-text
export MARCIANA_ADVERSARIAL_AKKA_FLUREE_CMD="$PWD/adapters/akka_fluree/run.sh"
export MARCIANA_ADVERSARIAL_LETTA_CMD="$PWD/adapters/letta/run.sh"
export MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS=1800
python3 run_benchmark.py --systems all
```

Each adapter's README documents its infrastructure and the rationale for
every capability it claims or declines.
