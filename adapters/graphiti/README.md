# Graphiti adapter

Runs MARCIANA-ADVERSARIAL-v1 against OSS
[graphiti-core](https://github.com/getzep/graphiti) (0.29.3) with local
Ollama models — no hosted APIs, no keys, no external database: storage uses
graphiti's embedded Kuzu driver.

## Setup

```sh
ollama pull llama3.1          # knowledge-graph extraction LLM
ollama pull nomic-embed-text  # embeddings

# environment (created automatically by run.sh on first use)
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python graphiti-core kuzu
```

## Standalone run

```sh
cd ../..   # repo root
python3 -c "import json; m=json.load(open('fixtures/marciana-adversarial-v1/manifest.json'))['manifest']['cases']; print(json.dumps({'protocol':'marciana-adversarial-adapter-v1','repeats':1,'cases':m}))" \
  | ./adapters/graphiti/run.sh
```

Or through the benchmark runner:

```sh
MARCIANA_ADVERSARIAL_GRAPHITI_CMD="$PWD/adapters/graphiti/run.sh" \
MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS=3600 \
python3 run_benchmark.py --systems marciana,graphiti
```

Every `remember` runs graphiti's knowledge-graph extraction through the
local LLM (~30 s per memory with `llama3.1` on a laptop), so a full pass
takes roughly 20–30 minutes.

## Mapping and claimed capabilities

Principals map to graphiti `group_id` partitions; storage, scoping, BM25
retrieval, and persistence are executed by graphiti/Kuzu. `remember` →
`add_episode` (bench id in the episode name, `valid_from` as
`reference_time`); `recall` → `search_` with graphiti's episode BM25 + RRF
recipe scoped to the principal's group; `forget` → `remove_episode`;
`restart` → close and reopen the client against the same on-disk database.

Claimed: `retrieval`, `isolation` (group partitions), `forget`,
`persistence` (on-disk Kuzu), `abstention` (episode BM25 returns nothing
without lexical overlap — graphiti's own behavior under a first-class
search recipe, not an adapter threshold).

Not claimed: `clearance`, `purpose`, `provenance`, `replay-protection`,
`idempotency`, `derived-tracking`, `supersession` — graphiti has no such
concepts; the driver reports those cases as unsupported rather than faking
them. `temporal` is not claimed either: graphiti is bi-temporal on
*extracted edges* (`valid_at`/`invalid_at` set by LLM date extraction), and
`SearchFilters` can filter on those dates, but the dates are inferred by
the extraction model rather than bound from a caller-controlled valid-time
interval, so an as-of query is only as reliable as the local LLM's date
extraction — with `llama3.1` that is not dependable enough to represent
the system's temporal semantics honestly.

## Backend notes

The repo's `docker-compose.yml` also provides Neo4j (graphiti's primary
backend) at `bolt://localhost:7687` (`neo4j`/`adversarial`); the adapter
was developed against the embedded Kuzu driver instead after the local
Docker daemon proved unreliable mid-benchmark, and Kuzu makes the run
self-contained. Two graphiti-core 0.29.3 Kuzu quirks are worked around in
`adapter.py`, both documented inline: full-text indexes are created
explicitly (`build_indices_and_constraints` is a no-op for Kuzu, and the
FTS extension must be installed/loaded), and `KuzuDriver` never initializes
the `_database` attribute that `add_episode` compares against the requested
`group_id`, so the adapter pins it before each write. Upstream deprecates
the Kuzu backend; switching the adapter back to Neo4j is a two-line change
in `_connect` once a reliable Neo4j is available.
