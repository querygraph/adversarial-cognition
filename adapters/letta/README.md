# Legacy Letta V1 archival API adapter

Runs MARCIANA-ADVERSARIAL-v1 against the self-hosted
[legacy Letta V1 server](https://github.com/letta-ai/letta), entirely locally:
Ollama embeddings, no LLM agent loop, no cloud keys.

This is not an adapter for the current
[Letta Agent](https://github.com/letta-ai/letta-code) or
[App Server](https://docs.letta.com/letta-agent/app-server). The current
product is a stateful agent runtime. Its memory includes MemFS, memory blocks,
context construction, compaction, and agent behavior. A native agent evaluation
must test those semantics.

## Setup

```sh
ollama pull nomic-embed-text        # embeddings (no LLM needed)
# Docker must be running; letta >= 0.13 requires Postgres, so this adapter
# uses the official letta/letta image, which bundles it.
```

Standalone run:

```sh
python3 -c "import json; m=json.load(open('fixtures/marciana-adversarial-v1/manifest.json'))['manifest']['cases']; print(json.dumps({'protocol':'marciana-adversarial-adapter-v1','repeats':1,'cases':m}))" \
  | ./adapters/letta/run.sh
```

Through the benchmark runner:

```sh
MARCIANA_ADVERSARIAL_LETTA_CMD=adapters/letta/run.sh python3 run_benchmark.py --systems marciana,letta
```

`run.sh` boots `letta/letta:0.16.8` (server + bundled Postgres), waits until
the archives endpoint answers steadily, runs `adapter.py` with
`letta-client==1.12.1`, and removes the container. First invocation pulls
the image (~3 GB). Steady-state boot is ~25–40 s; the full suite takes
~2–4 min, dominated by Ollama embedding calls (~100–350 ms per case).

## Mapping

One archive per benchmark principal keeps case data partitioned. The adapter
inserts and searches passages through the archival API. Every request uses the
same Letta client and organization-scoped actor. This actor can select any
archive ID. The archive mapping does not enforce caller authorization.

Bench IDs ride in a `[id:…]` text marker plus passage metadata. `valid_from`
becomes the passage `created_at`; an as-of recall becomes a search `end_date`.
The archive embedding is configured explicitly as an OpenAI-compatible
endpoint (`…:11434/v1`) because letta 0.16's `ollama/…` handle resolution
points its OpenAI client at the raw Ollama base URL, which 404s.

## Capabilities claimed

| Capability | Why |
|---|---|
| `retrieval` | Archival semantic search, ranked |
| `temporal` | `created_at` + search `start_date`/`end_date` windows (validity **end** is inexpressible — a superseded fact stays searchable at later as-of dates, so `retrieval-current` genuinely tests ranking with both facts present) |
| `forget` | Passage deletion |
| `persistence` | Server-side Postgres; client reconnect must observe identical state |

Unclaimed (declared unsupported, 12 cases): caller isolation, abstention (no
relevance threshold in the search API), clearance, purpose, provenance
digests, nonce replay protection, idempotency keys, and derived-memory
tracking.

## Recorded result (2026-08-06, legacy Letta V1 server 0.16.8)

6 supported cases, **4 correct**. Passing: retrieval-current (ranking preferred
the current fact with the superseded one present), temporal-history,
restart-reproducible, and order-invariant. Honest failures: `malformed-empty`
and `oversized-query` — the V1 server embeds an empty and a 24 KB query and
returns ranked results instead of rejecting either.
