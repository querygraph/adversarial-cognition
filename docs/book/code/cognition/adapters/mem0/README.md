# Mem0 OSS adapter

Runs MARCIANA-ADVERSARIAL-v1 against the open-source
[mem0](https://github.com/mem0ai/mem0) package (`mem0ai==2.0.17`), fully
locally: Chroma on disk for vectors, Ollama for embeddings. No API keys.

## Setup

```sh
# Ollama must be running with the embedding model pulled:
ollama pull nomic-embed-text
# (llama3.1 is configured as mem0's LLM but never invoked: storage uses
#  infer=False, so no generation happens in this adapter.)
```

`uv` provisions the pinned Python 3.12 environment on first run.

## Run standalone

```sh
python3 -c "import json; m=json.load(open('fixtures/marciana-adversarial-v1/manifest.json'))['manifest']['cases']; print(json.dumps({'protocol':'marciana-adversarial-adapter-v1','repeats':1,'cases':m}))" \
  | ./adapters/mem0/run.sh
```

Wire into the benchmark with:

```sh
export MARCIANA_ADVERSARIAL_MEM0_CMD="$PWD/adapters/mem0/run.sh"
```

## Capability claims

| Capability | Rationale |
|------------|-----------|
| `retrieval` | `memory.search` over Chroma with Ollama embeddings |
| `isolation` | mem0's own `user_id` scoping; each principal is a separate user |
| `forget` | `memory.delete` by mem0 id (bench ids mapped via metadata) |
| `persistence` | on-disk Chroma + history DB; restart reopens the same store |
| `abstention` | mem0's own `search(threshold=…)` relevance floor (0.55, calibrated for nomic-embed-text on this corpus: genuine matches score 0.60–0.83, the unrelated probe peaks at 0.48); the cutoff is applied by mem0, not by adapter post-filtering |
| `temporal` (partial) | mem0 OSS's own `expiration_date` mechanism hides expired memories at search time, which answers current-validity queries; historical as-of queries (`reference_date`) are platform-only in mem0 OSS, so `temporal-history` raises Unsupported and is reported as such |

Not claimed (no corresponding OSS API): clearance, purpose binding,
provenance/source digests, nonce replay protection, idempotency keys,
derivation tracking, supersession (`infer=True` LLM-decided updates exist
but are nondeterministic with a local model and were not relied on).

## Recorded standalone result (2026-08-06, mem0ai 2.0.17)

Supported 9 of 18; 7 pass, 2 fail:

- **fail `malformed-empty`** — mem0 raises `ValueError` on an empty query
  instead of gracefully abstaining.
- **fail `oversized-query`** — a 24 KB query is accepted and embedded; mem0
  applies no input bound, where the benchmark expects rejection.

Unsupported (declared, excluded from accuracy): temporal-history,
isolation-clearance, purpose-denial, forged-source, stale-proposal,
replay-mutation, replay-restart, idempotent-retry, forget-derived.

Implementation notes: storage uses `infer=False` with a `bench_id` metadata
key mapped back at search time; each case runs in a fresh per-epoch store
path because chromadb caches clients per path (a deleted-and-recreated
directory would collide with the cached handle); `MEM0_TELEMETRY=false`
keeps PostHog quiet; all library output is kept on stderr so stdout carries
only the protocol JSON.
