# Letta 0.16 legacy archive-search adapter

Runs a limited MARCIANA-ADVERSARIAL-v1 integration against the legacy
archive/passage API in `letta/letta:0.16.8`, entirely locally. It pins
`letta-client==1.12.1` and deliberately bypasses the agent loop. It is **not**
representative of Letta's current app server, agent loop, or memory behavior.
For current self-hosting, see [Letta's app-server documentation](https://docs.letta.com/self-hosting).

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

The adapter creates one archive per benchmark principal and chooses the
corresponding `archive_id` before each search. This is adapter-side routing,
not differential authorization enforced by Letta, and therefore does not
claim or test the benchmark's isolation capability. Passages are inserted and
searched through the archival API only. Bench IDs ride in a `[id:…]` text
marker plus passage metadata. `valid_from` becomes the passage
`created_at`; an as-of recall becomes a search `end_date`. The archive
embedding is configured explicitly as an OpenAI-compatible endpoint
(`…:11434/v1`) because letta 0.16's `ollama/…` handle resolution points its
OpenAI client at the raw Ollama base URL, which 404s.

## Capabilities claimed

| Capability | Why |
|---|---|
| `retrieval` | Archival semantic search, ranked |
| `temporal` | `created_at` + search `start_date`/`end_date` windows (validity **end** is inexpressible — a superseded fact stays searchable at later as-of dates, so `retrieval-current` genuinely tests ranking with both facts present) |
| `forget` | Passage deletion |
| `persistence` | Server-side Postgres; client reconnect must observe identical state |

Unclaimed (declared unsupported, 12 cases): isolation and authorization,
abstention (no relevance threshold in the search API), clearance, purpose,
provenance digests, nonce replay protection, idempotency keys, and
derived-memory tracking.

## Historical observation (not a published comparative score)

An earlier local run of the legacy path reported four correct results among
the six cases it can legitimately claim: current and historical retrieval,
restart reproducibility, and order invariance. The two misses were
`malformed-empty` and `oversized-query`: the endpoint accepted an empty query
and the benchmark's 24 KiB (`"price " * 4096`) query. These are input-validation
observations only, not memory-disclosure or authorization findings. The raw
Letta output was not committed, so this observation is not included in the
published comparative results pending a fresh, auditable capture.
