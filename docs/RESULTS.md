# Recorded results

**Benchmark:** MARCIANA-ADVERSARIAL-v1
**Date:** 2026-08-06
**Reference host:** Darwin arm64, Python 3.14, local Ollama (`gpt-oss:20b`,
`nomic-embed-text`), Fluree `fluree/server` 4.1.4, Letta 0.16.8.

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
| Letta 0.16.8 | 9 | 7 | 78% | 9 | No input-robustness boundary (see below) |
| Mem0 (OSS) | — | — | — | — | Run in progress |
| Graphiti (Kuzu) | — | — | — | — | Run in progress |
| Cognee (OSS) | — | — | — | — | Run in progress |

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

## Letta 0.16.8 — 7/9 supported correct

Letta's archival-memory path (archives + passages, Ollama embeddings, no LLM
agent loop) provides retrieval, isolation (one archive per principal),
temporal (`created_at`/`end_date`), forget, and persistence. Passing:
current and historical retrieval, tenant isolation, restart reproducibility,
order invariance, injection containment.

**Two genuine failures — a real finding, not an adapter bug:**

- `malformed-empty`: an empty query returns *all* memories instead of
  abstaining. Letta's semantic search has no empty-query guard.
- `oversized-query`: a 16 KB query is accepted and answered rather than
  rejected. Letta's archival search has no input bound.

Both cases require only the `retrieval` capability Letta claims, so they are
scored — and Letta has no input-robustness boundary at the memory layer.

**Declared unsupported (9):** abstention (semantic search always returns
nearest neighbors, no relevance threshold), clearance, purpose, provenance,
replay, idempotency, and forget-with-derived — none of which Letta's memory
API enforces.

## Reproducing

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
