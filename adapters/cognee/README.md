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

Ingestion (cognify) is LLM-driven and runs per case on a clean store;
expect tens of minutes with local models, hence the timeout override.

## Capability rationale

Claimed: `retrieval` (CHUNKS vector search), `isolation` and `clearance`
(cognee's native dataset scoping: `org-shared`/`org-private` tiers plus
per-principal `own-*` datasets; scope selection is caller-supplied, the same
trust shape as any user-scoped OSS memory API — cognee's backend
access-control mode exists but is disabled here for a single-process run),
`persistence` (file-backed stores survive `disconnect`).

Not claimed: temporal/as-of recall (validity windows are not expressible),
abstention (CHUNKS returns nearest neighbors with no native threshold),
purpose binding, digest-bound improvement, replay protection, idempotency
keys, derivation tracking. `cognee.delete` provides item-level deletion, but
without derivation tracking no runnable case exercises it, so `forget` stays
unclaimed. A future adapter could try `remember(self_improvement=True)` as a
supersession path for `retrieval-current`.

Notable behaviors observed: cognee raises `ValueError` on an empty query and
happily embeds an oversized (24 KB) one, so `malformed-empty` and
`oversized-query` fail honestly; a search over a principal with no datasets
returns a 404, which the adapter reports as an empty result (non-disclosure).

## Standalone check

```sh
python3 -c "import json; m=json.load(open('fixtures/marciana-adversarial-v1/manifest.json'))['manifest']['cases']; print(json.dumps({'protocol':'marciana-adversarial-adapter-v1','repeats':1,'cases':m}))" > /tmp/cognee-req.json
cat /tmp/cognee-req.json | ./adapters/cognee/run.sh
```
