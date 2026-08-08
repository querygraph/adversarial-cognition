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

## Reading ranked IDs

`recall()` is called with `auto_route=True`, so cognee's own classifier picks
the retrieval strategy per query instead of the adapter pinning one.

cognee answers in prose. Passing `include_references=True` appends the source
chunks that produced the answer, most relevant first; the adapter parses
memory IDs out of that evidence list only, so the ordering scored by the
benchmark is cognee's own, not a re-ranking by the adapter.

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
  retriever it does not return at all. `recall` is therefore bounded by
  `MARCIANA_COGNEE_RECALL_TIMEOUT` (default 180 s) so a non-returning query
  fails its own case instead of stalling the suite. `malformed-empty` fails
  either way.
- cognee embeds an oversized (24 KB) query rather than bounding it, so
  `oversized-query` fails honestly.

Both are real gaps rather than adapter artifacts, and both are reported
upstream.

`injection-contained` also fails, and the reason is worth stating plainly:
the boundary holds — the injected instruction does not reach `private-farm`
in any run — but the injected memory no longer ranks first. Claiming
`temporal` makes the driver supply an as-of date on *every* recall, including
the robustness cases, and an as-of-qualified query ranks the dated price
facts above the injected text. Pinning `retrieval` only would pass this case
and lose the two temporal ones; the honest capability set is kept.

## Standalone check

```sh
python3 -c "import json; m=json.load(open('fixtures/marciana-adversarial-v1/manifest.json'))['manifest']['cases']; print(json.dumps({'protocol':'marciana-adversarial-adapter-v1','repeats':1,'cases':m}))" > /tmp/cognee-req.json
cat /tmp/cognee-req.json | ./adapters/cognee/run.sh
```
