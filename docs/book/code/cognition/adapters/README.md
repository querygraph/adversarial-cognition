# OSS system adapters

Each adapter runs MARCIANA-ADVERSARIAL-v1 against one open-source memory
system. All adapters share [`protocol.py`](protocol.py): a system implements
the small `MemorySystem` interface and declares the capabilities it genuinely
provides. The driver replays each benchmark case **behaviorally** (inputs,
an as-of date, forbidden IDs) against the system's own API, scores against
the expectations shipped in the request, and marks any case whose required
capability the system does not claim as `"supported": false` — it never
fakes a result for a missing feature.

## Design stance: honest capability, not fake security

None of these OSS systems ships the full governed boundary the benchmark
tests. That is the point of the exercise, and the adapters make it visible
rather than hiding it. Every adapter:

- claims only capabilities its system actually enforces (see each README's
  capability table), and declares the rest unsupported;
- executes authorization, temporal, ranking, and mutation semantics through
  the **system's own API**, never re-implementing a security check the
  system lacks; and
- reports its own `adapter_version`, recorded verbatim in the benchmark
  report.

Unsupported cases are counted separately and never scored as passes,
failures, or gate violations — so a system is measured on what it claims,
and a claim it cannot back is a benchmark failure, not silent success.

## Running

Every adapter is a stdin→stdout command wired to the benchmark through an
environment variable:

```sh
docker compose up -d                       # Neo4j (Graphiti) + Fluree (Akka)
export MARCIANA_ADVERSARIAL_AKKA_FLUREE_CMD="$PWD/adapters/akka_fluree/run.sh"
export MARCIANA_ADVERSARIAL_MEM0_CMD="$PWD/adapters/mem0/run.sh"
export MARCIANA_ADVERSARIAL_GRAPHITI_CMD="$PWD/adapters/graphiti/run.sh"
export MARCIANA_ADVERSARIAL_COGNEE_CMD="$PWD/adapters/cognee/run.sh"
export MARCIANA_ADVERSARIAL_COGNEE_RS_CMD="$PWD/adapters/cognee_rs/run.sh"
export COGNEE_RS_BIN=/path/to/cognee-cli
export MARCIANA_ADVERSARIAL_LETTA_CMD="$PWD/adapters/letta/run.sh"
export MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS=1800   # local LLMs are slow
python3 run_benchmark.py
```

The LLM-backed adapters (Mem0, Graphiti, Cognee, Letta) install their own
dependencies into an isolated `uv` environment on first run and drive
[Ollama](https://ollama.com) locally:

```sh
ollama pull llama3.1 && ollama pull nomic-embed-text
```

The Akka + Fluree adapter is standard-library only and needs just the Fluree
container. See `RESULTS.md` for the recorded run and
per-system status.

| Adapter | Infrastructure | Backend |
|---------|----------------|---------|
| akka_fluree | Fluree container (`docker compose`) | Fluree semantic ledger over HTTP; stdlib-only |
| mem0 | Ollama | Mem0 OSS with a local vector store |
| graphiti | Ollama | graphiti-core over embedded Kuzu (no external DB) |
| cognee | Ollama | Cognee OSS knowledge graph + vector index |
| cognee_rs | Native Rust CLI + Ollama | Official cognee-rs memory engine |
| letta | Letta App Server + Agent SDK + Ollama | Agent-loop memory over persistent MemFS |

Each adapter's own README and module docstring is the authoritative record
of the capabilities it claims and the rationale for each — they are tuned to
what the system actually enforces as we verify it locally. The recurring
pattern is that these systems provide retrieval, isolation, and persistence
natively but do not ship the provenance-digest binding, nonce/idempotency
ledger, or (mostly) the clearance/purpose policy engine the benchmark tests
— so those cases are declared unsupported rather than faked.
