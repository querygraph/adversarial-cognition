# Adversarial Benchmarks — Current Results

**Companion to the book *Adversarial Cognition*.**

This report holds the *current* numbers the book deliberately leaves out. The
book explains what each benchmark reveals and treats its systems as examples;
this report records how each system scored on the latest run. It is regenerated
whenever a suite runs and stamped with the corpus digest that proves which corpus
produced it. When numbers here disagree with an older copy, this one wins — that
is the entire point of keeping them here rather than in the book.

Every run is scored the same way. **Coverage** is how many cases a system's
adapter *declares* it enforces; **correctness** is how many of those it got
right. A capability a system does not claim is *unsupported* — never a pass,
never a failure. **Hard gates** are named safety properties that must be zero;
no quality score buys one back. Scores taken over different coverage are not
directly comparable.

---

## Cognition — MARCIANA-ADVERSARIAL-v1

**Corpus digest:** `sha256:d879b8a53039d84134bf8b35f21a398c497b94605bddf1a4995854aa1cb798b9`
· **Profile:** adversarial-v1-comparative on local-ollama · **Source of truth:**
`adversarial-cognition/docs/RESULTS.md`

Comparative systems run through their own open-source stacks with local models
(Ollama) and local infrastructure — no cloud keys. LLM-backed systems vary by
host and model; the ledger and reference runs are deterministic.

| System | Coverage | Correct within coverage | Adapter |
|--------|:--------:|:-----------------------:|---------|
| Marciana | 18/18 | 100% (18/18) | governed reference |
| Akka + Fluree | 16/18 | 100% (16/16) | Fluree server 4.1.4 |
| Graphiti | 8/18 | 75% (6/8) | graphiti-core 0.29.3 · Kuzu |
| Cognee | 10/18 | 70% (7/10) | cognee-oss |
| Mem0 | 9/18 | 67% (6/9) | mem0-oss |
| Letta | 6/18 | 17% (1/6) | app-server + Agent SDK 0.6.2 · llama3.1 |
| cognee-rs | 4/18 | 0% (0/4) | cognee-rs native CLI (v0.2.0) |

**Marciana hard gates — all zero:** `unauthorized_disclosure`,
`cross_scope_leakage`, `invalid_provenance_accepted`, `stale_proposal_committed`,
`replayed_mutation_accepted`, `duplicate_durable_mutation`,
`residual_recall_after_forget`, `non_deterministic_receipts`,
`adversarial_input_mishandled`.

Notes on this run: Mem0's only scoping axis is `user_id`, so an intra-tenant
clearance difference leaks (`isolation-clearance` fails). Graphiti fails
`order-invariant` and `oversized-query`. Cognee errors on the empty query and on
injection/confusable/oversized cases, but its dataset tiers do withhold private
data (`isolation-clearance` passes). Letta returns no bounded IDs across most
cases and clears only empty-query abstention. cognee-rs claims only native
retrieval and persistence, declares its dataset name is not an authorization
boundary, and on this build does not yet hold determinism or bound its inputs.

---

## Catalog — CATALOG-PROVENANCE-v1

**Corpus digest:** `sha256:71bb8c267867497f6c93d6ef2496d5fad09f22fd87b7f177bd48cc65844b697d`
· **Run:** all catalogs writing to one MinIO through Docker · **Source of truth:**
`catalog-provenance/docs/RESULTS.md`

| Catalog | Supported | Correct | Unsupported | Gates |
|---------|:---------:|:-------:|:-----------:|:-----:|
| reference (LakeCat's boundary) | 17 | 17 | 0 | 0 |
| Nessie 0.107.5 | 3 | 3 | 14 | 0 |
| Polaris 1.5.0 | 3 | 3 | 14 | 0 |
| Gravitino | 3 | 3 | 14 | 0 |

Every stock catalog holds `commit` and `compare-and-swap` and declines the
eleven governance capabilities; the governed reference holds all of them, every
gate zero. Unity Catalog OSS is excluded: its Iceberg REST surface is read-only.

### Catalog speed — catalog-bench (companion performance suite)

**Source of truth:** `catalog-bench/RESULTS.md`. Same four catalogs, one shared
MinIO, identical minimal commits — 1000 sequential for latency, then 8 concurrent
writers for throughput.

| Catalog | Seq throughput | Seq p50 | Concurrent (8w) | Conflict rate |
|---------|:--------------:|:-------:|:---------------:|:-------------:|
| Nessie 0.107.5 | 170.6 /s | 4.87 ms | 136.3 /s | 82.1% |
| LakeCat 0.2.1 | 148.6 /s | 5.34 ms | 288.0 /s | 70.2% |
| Gravitino | 132.4 /s | 6.34 ms | 272.6 /s | 0% |
| Polaris 1.5.0 | 84.0 /s | 10.40 ms | 61.5 /s | 7.5% |

LakeCat: #2 sequential, #1 concurrent — paying for features, not losing on speed.
Absolute figures are per-run; read them within a run, not across rounds.

---

## Capability — CAPABILITY-ADVERSARIAL-v1

**Corpus digest:** `sha256:2ac14b830936da9bb2f7606dbfc2ed2a21ac2ff34796c881b5aef1c45ceb5733`
· **Run:** every adapter live over its system's real library · **Source of truth:**
`adversarial-capability/docs/RESULTS.md`

| System | Band | Claimed & correct | Gates |
|--------|------|:-----------------:|:-----:|
| reference | idealized boundary | 18 / 18 | 0 |
| TypeSec | capability system | 17 / 18 | 0 |
| Biscuit | capability token | 8 / 18 | 0 |
| Macaroons | capability token | 6 / 18 | 0 |
| UCAN | capability token | 3 / 18 | 0 |
| JWT / OAuth | bearer floor | 6 / 18 | 0 |
| Cedar | policy engine | 4 / 18 | 0 |
| OPA | policy engine | 4 / 18 | 0 |
| OpenFGA | ReBAC | 4 / 18 | 0 |
| SpiceDB | ReBAC | 4 / 18 | 0 |

Every system holds every capability it claims; all gates zero. TypeSec declines
only `wire-integrity` (the capability core has no request wire), which no real
system in the field claims either. Decision engines cluster; the token band
climbs by its cryptography; only the capability system spans the boundary.

---

*Generated from each benchmark's machine-readable report. To reproduce any table,
run that benchmark's Docker stack; the corpus digest above will match.*
