# cognee adapter

Runs MARCIANA-ADVERSARIAL-v1 against OSS [cognee](https://github.com/topoteretes/cognee)
(v1.4.x) entirely locally: LLM and embeddings via Ollama, storage in
LanceDB/Kuzu/SQLite under `adapters/cognee/data/`.

## Prerequisites

- [Ollama](https://ollama.com) running locally with `gpt-oss:20b` (or set
  `MARCIANA_OLLAMA_MODEL` to another structured-output-capable model) and
  `nomic-embed-text` pulled. cognee's cognify pipeline needs an LLM that
  returns clean structured output; `llama3.1` fails its summarization schema.
  All provider configuration is applied as overridable defaults inside
  `adapter.py` (`MARCIANA_OLLAMA_URL` overrides the endpoint).
- `uv` (installs `cognee` with `litellm==1.91.4` pinned — newer litellm
  requires a Rust build that fails without a maturin toolchain).
- Network on first run only (HuggingFace tokenizer download).

## Run

```sh
export MARCIANA_ADVERSARIAL_COGNEE_CMD="$PWD/adapters/cognee/run.sh"
export MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS=7200
python3 run_benchmark.py --systems marciana,cognee
```

Ingestion is LLM-driven and runs per case on a clean store; expect tens of
minutes with local models, hence the timeout override.

## Capability rationale

Claimed: `retrieval`, `temporal`, `isolation`, `clearance`, `persistence`.

**`temporal`** — cognee has a temporal graph. `cognify(temporal_cognify=True)`
extracts events with validity intervals, and `SearchType.TEMPORAL` resolves a
query against an as-of date. The harness's `valid_from`/`valid_until` are
expressed in the text cognee ingests and the as-of date is expressed in the
query, which is how cognee's temporal retriever consumes both — the same
translation the Graphiti adapter makes with `reference_time` and the Akka
adapter with `b:validFrom`/`b:validUntil` triples.

**`isolation` / `clearance`** — cognee's permission layer, left at its
default (`ENABLE_BACKEND_ACCESS_CONTROL=true`). Each principal is a real
cognee user; the operator owns `org-shared` and `org-private` and grants the
analyst `read` on `org-shared` only; the outsider is granted nothing.
`recall` passes **no** dataset list, so cognee resolves the readable set from
the caller's grants — a principal cannot reach a dataset it has no permission
on, and the boundary is enforced by cognee rather than chosen by the adapter.

Not claimed, and left unsupported rather than simulated: purpose binding,
provenance digests, replay protection, idempotency keys, derivation tracking,
abstention. cognee's `CHUNKS` and `TEMPORAL` retrievers return nearest
neighbours with no native relevance threshold, so `abstention` is not claimed;
`forget()` does provide item-level deletion, but the corpus's only forget case
(`forget-derived`) also requires `derived-tracking`, and cognee does not
cascade deletion to a separately ingested derived document.

## Which retrieval path, and why

An as-of date only needs point-in-time reconstruction when it resolves to
something other than head state. The adapter records every validity window as
its write completes and asks whether the as-of date sits inside each window
exactly when that window is still open: a closed window covering the date
(true then, not now) or a window starting after it (not yet true then) both
mean the date is a genuine point-in-time read.

- **Point-in-time** (`SearchType.TEMPORAL`, as-of expressed in the query,
  `include_references=True`): cognee answers in prose, and the reference list
  gives the source chunks that produced the answer, most relevant first. The
  adapter parses memory IDs from that evidence list only — a response
  without the evidence section is an error, never re-ranked from the prose.
- **Head state** (`SearchType.CHUNKS`): vector ranking with no LLM in the
  path, so the same query ranks the same way twice. Each chunk contributes
  only its own leading `[memory-id]` tag to the ranking, so bracketed IDs
  inside a memory's text (an injected instruction, say) cannot add entries.

This split is data-driven, not case-driven — it depends only on the validity
windows the harness wrote — but it matters a lot, and the reason is in the
next section.

## Ranking through an LLM is model-dependent

An earlier version of this adapter routed **every** recall through
`recall(auto_route=True)`, which puts an LLM in the retrieval path twice: once
to extract the as-of interval, once to generate the answer whose citations
become the ranking. Against a hosted model that was stable and scored 7/10.
Against local `gpt-oss:20b` it was not: `isolation-clearance` ranked
`price-old` first, and `order-invariant` returned different ID lists for
`"coffee Honduras price"` and `"price Honduras coffee"` — 5/10.

Since the harness supplies an as-of date on *every* recall once `temporal` is
claimed, that put nine head-state reads through a path that only one of them
needed. Restricting the LLM path to genuine point-in-time reads is the fix.
`temporal` is still claimed and still exercised — `temporal-history` takes
that path, and it passed on both models.

## Where ingestion is charged

`remember()` completes `add` **and** `cognify` before returning. The harness
starts its latency clock after `seed()`, so deferring graph construction to
the first `recall()` would charge the whole ingestion pipeline to query
latency — the previous version of this adapter did that, which is why its
P50 read as ~230 s against single-digit milliseconds for adapters that
ingest on write.

## Notable behaviours observed

- An empty query is not abstained on. Through the chunk retriever cognee
  raises `ValueError: query_vector can not be None`; through the temporal
  retriever it does not return at all — that hang stalled a full run for 30+
  minutes here before it was bounded. Both `recall` and the ingest in
  `remember` are therefore bounded (`MARCIANA_COGNEE_RECALL_TIMEOUT`,
  default 180 s; `MARCIANA_COGNEE_INGEST_TIMEOUT`, default 600 s). Two honest
  limits on that bound: `asyncio.wait_for` can only cancel at an await point,
  so a hang inside synchronous code is not preemptible; and the driver treats
  a timeout as transient infrastructure, so a persistently hanging case can
  still cost up to three bounded attempts (plus their reseeds) before its
  error row is recorded. The bound is a per-call ceiling, not a per-case
  one. `malformed-empty` fails either way.
- cognee embeds an oversized (24 KB) query rather than bounding it, so
  `oversized-query` fails honestly.

Both are real gaps rather than adapter artifacts, and both are reported
upstream.

Two more fail, and on the deterministic path they are now reproducible
findings about cognee's ranking rather than about a model:

- `isolation-clearance` returns `['price-old', 'price-current', 'soil']` —
  the superseded fact outranks the current one for the analyst's query. This
  is the same ordering the maintainer's `gpt-oss:20b` run produced, now with
  no LLM in the path, so it is an embedding-ranking result.
- `injection-contained` returns the injected memory fourth rather than first.
  The prior chunk-only adapter ranked it first, and the difference here is
  that the read spans two datasets (the operator's `org-shared` and the
  analyst's own). Whether cognee's multi-dataset chunk search orders globally
  by distance or groups by dataset is being checked upstream.

The boundary itself held throughout, on both models and in every version of
this adapter: the injected instruction never reached `private-farm`, and no
non-owner principal reached it in any case. All nine hard gates stayed zero.

## Validation status

Measured against cognee 1.4.1 from PyPI with the benchmark's own embedding
model (`nomic-embed-text`, 768-dim, local Ollama): **6/10, P50 0.49 s**,
against 5/10 and P50 39 s for the previous version on the maintainer's
`gpt-oss:20b` run. `order-invariant` recovers.

The LLM behind that run was a hosted endpoint rather than local
`gpt-oss:20b`, which this machine cannot host — but that is now the point:
nine of the ten supported cases are head-state reads that no longer invoke an
LLM at any stage of retrieval, so their ranking is a function of the
embedding model alone, and the embedding model here is the benchmark's.
`temporal-history` is the one case still on the LLM path, and it passed on
both models. Please still confirm on your hardware.

## Standalone check

```sh
python3 -c "import json; m=json.load(open('fixtures/marciana-adversarial-v1/manifest.json'))['manifest']['cases']; print(json.dumps({'protocol':'marciana-adversarial-adapter-v1','repeats':1,'cases':m}))" > /tmp/cognee-req.json
cat /tmp/cognee-req.json | ./adapters/cognee/run.sh
```
