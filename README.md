# adversarial-cognition

**MARCIANA-ADVERSARIAL-v1** — a deterministic adversarial cognition benchmark
for AI memory systems. It tests not whether a system retrieves a fact, but
whether it stays **correct, secure, auditable, and reproducible when the
memory and the request path are actively trying to mislead it**: forged
provenance, stale proposals, replayed mutations, cross-tenant probes,
Unicode confusables, prompt injection, oversized input, and restarts at
inconvenient moments.

Extracted from [querygraph/marciana](https://github.com/querygraph/marciana)
(at `cbf3592`), where it gates releases; it now lives here as a standalone,
dependency-free benchmark any memory system can run against.

## Release policy

Safety failures are counted in nine named **hard gates that must all be
zero** — they are never averaged into a quality score:

`unauthorized_disclosure`, `cross_scope_leakage`,
`invalid_provenance_accepted`, `stale_proposal_committed`,
`replayed_mutation_accepted`, `duplicate_durable_mutation`,
`residual_recall_after_forget`, `non_deterministic_receipts`,
`adversarial_input_mishandled`.

Quality (accuracy by category, abstention behavior) and performance
(P50/P95/P99, formation, restart) are reported separately.

## Quick start

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -q
python3 run_benchmark.py
```

No dependencies, no network, no keys. The runner verifies the corpus against
its versioned manifest (`fixtures/marciana-adversarial-v1/manifest.json`,
regenerated with `--pin-corpus`), runs the deterministic reference backend
twice to gate receipt determinism, and exits non-zero unless every hard gate
is zero.

## Reproduce the full benchmark in Docker

The whole comparative benchmark — every system, wired to its own service — is
packaged as a Docker stack. On a host with [Ollama](https://ollama.com)
running and the models pulled:

```sh
ollama pull gpt-oss:20b nomic-embed-text   # cognee needs the 20B model
docker compose build
docker compose run --rm benchmark          # runs all systems → ./out/RESULTS.md
```

`docker compose` brings up Fluree and Letta as services; the `benchmark`
container resolves each adapter's pinned dependencies (baked into the image),
runs every system against the corpus, and writes the report and
`RESULTS.md` into `./out`. By default it uses the host's Ollama (fast, GPU
accelerated on macOS/Windows). For a fully self-contained stack on a Linux
GPU host, start the bundled Ollama instead:

```sh
docker compose --profile bundled-ollama up -d ollama
docker compose exec ollama ollama pull gpt-oss:20b nomic-embed-text
MARCIANA_OLLAMA_URL=http://ollama:11434 docker compose run --rm benchmark
```

Run a subset by passing the `--systems` value: `docker compose run --rm
benchmark marciana,akka-fluree`. The LLM-backed systems (Mem0, Graphiti,
Cognee, Letta) depend on the local model and hardware, so their numbers vary
by host; the reference and Akka+Fluree runs are deterministic.

## The corpus

Eighteen cases across eleven categories — retrieval, temporal, abstention,
authorization, provenance, mutation, replay, recovery, forget,
reproducibility, robustness — each with explicit expectations: an expected
decision, an expected ranked prefix, a mandatory-abstention flag, and
forbidden IDs that must never appear. The corpus is versioned by content
digest; the runner refuses to execute a corpus that does not match its pin.
Full design: [`docs/MARCIANA-ADVERSARIAL-v1.md`](docs/MARCIANA-ADVERSARIAL-v1.md).
The public overview is at [adversari.al/cognition](https://adversari.al/cognition),
and the companion book is available through
[FirstPair](https://firstpair.org/read/adversarial-cognition/). Ownership and
build paths for those separate repositories are recorded in
[`FIRSTPAIR.md`](FIRSTPAIR.md).

## Comparative systems

Every configured system is enumerated on every run — `executed`, `error`, or
`unavailable` with the missing configuration named — and never silently
substituted. External systems run only through explicitly configured
commands:

| System | Command variable | OSS adapter |
|--------|------------------|-------------|
| Mem0 | `MARCIANA_ADVERSARIAL_MEM0_CMD` | [`adapters/mem0/`](adapters/mem0/) |
| Zep | `MARCIANA_ADVERSARIAL_ZEP_CMD` | — (hosted; bring your own) |
| Letta App Server | `MARCIANA_ADVERSARIAL_LETTA_CMD` | [`adapters/letta/`](adapters/letta/) |
| Cognee | `MARCIANA_ADVERSARIAL_COGNEE_CMD` | [`adapters/cognee/`](adapters/cognee/) |
| Graphiti | `MARCIANA_ADVERSARIAL_GRAPHITI_CMD` | [`adapters/graphiti/`](adapters/graphiti/) |
| Akka + Fluree | `MARCIANA_ADVERSARIAL_AKKA_FLUREE_CMD` | [`adapters/akka_fluree/`](adapters/akka_fluree/) |

An adapter receives the case corpus as JSON on stdin and prints one outcome
per case. It may report its own `adapter_version` (recorded verbatim) and
may honestly declare a case `"supported": false` — unsupported cases are
counted separately and never scored as passes, failures, or gate
violations. The OSS adapters here run entirely locally: LLM and embedding
calls go to [Ollama](https://ollama.com) (`llama3.1`, `nomic-embed-text`),
and infrastructure (Neo4j for Graphiti, Fluree for the Akka adapter) comes
from `docker compose up -d`. Setup details live in each adapter's README.
The bundled Letta adapter uses the current TypeScript Agent SDK and self-hosted
App Server. Remember, recall, and forget operations all execute through the
agent loop and persistent MemFS.
Bounded raw outputs underlying published comparative results are committed in
[`outputs/`](outputs/). A system without a retained output is not assigned a
published score.
`MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS` overrides the per-adapter timeout
(default 600) for slow local models.

Public corpora (LoCoMo, LongMemEval, BEAM, DMR, Letta-Evals) are
inventoried at pinned source revisions and normalized offline only from
explicitly configured `MARCIANA_ADVERSARIAL_<CORPUS>_PATH` fixtures —
nothing is downloaded at run time.

## Fairness

The benchmark is authored by one of the systems it measures, so the design
answers the objections we would raise ourselves: gates encode
system-agnostic obligations, cases are expressed behaviorally, unconfigured
systems are never scored, failing adapters are never converted into
results, performance is never cross-normalized between in-process and
hosted systems, and vendor-authored adapters are first-class. The full
fairness policy is in the
[benchmark document](docs/MARCIANA-ADVERSARIAL-v1.md).

## License

MIT or Apache-2.0, at your option.
