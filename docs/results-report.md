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

| System | Interface | Coverage | Correct within coverage | Adapter |
|--------|-----------|:--------:|:-----------------------:|---------|
| Marciana | direct-api | 18/18 | 100% (18/18) | governed reference |
| Akka + Fluree | direct-api | 16/18 | 100% (16/16) | Fluree server 4.1.4 |
| Graphiti | direct-api | 8/18 | 75% (6/8) | graphiti-core 0.29.3 · Kuzu |
| Mem0 | direct-api | 9/18 | 67% (6/9) | mem0-oss |
| Cognee | direct-api | 10/18 | 50% (5/10) | cognee-oss |
| Letta | agent-loop | 6/18 | 17% (1/6) | app-server + Agent SDK 0.6.2 · llama3.1 |
| cognee-rs | direct-api | 4/18 | 0% (0/4) | cognee-rs native CLI (v0.2.0) |

The `interface` column records how each adapter reached its system's memory
(`direct-api` vs `agent-loop`); MARCIANA-ADVERSARIAL-v2 promotes it to a
comparison *track* (`docs/MARCIANA-ADVERSARIAL-v2.md`). It is metadata, not a
score — the adapter enforces no gate either way.

**Marciana hard gates — all zero:** `unauthorized_disclosure`,
`cross_scope_leakage`, `invalid_provenance_accepted`, `stale_proposal_committed`,
`replayed_mutation_accepted`, `duplicate_durable_mutation`,
`residual_recall_after_forget`, `non_deterministic_receipts`,
`adversarial_input_mishandled`.

Notes on this run: Mem0 holds tenant isolation and deterministic recall but
does not claim clearance-level scoping (`isolation-clearance` is unsupported,
its only axis being `user_id`) and fails all three adversarial-input cases
(`oversized-query`, `confusable-query`, `injection-contained`). Graphiti fails
`order-invariant` and `oversized-query`. Cognee errors on the empty query and
fails `isolation-clearance`, `order-invariant`, and `injection-contained`,
though on this run it does contain the confusable query. Letta returns no
bounded IDs across most cases and clears only empty-query abstention. cognee-rs
claims only native retrieval and persistence, declares its dataset name is not
an authorization boundary, and on this build does not yet hold determinism or
bound its inputs.

## Cognition — MARCIANA-ADVERSARIAL-v2

**Corpus digest:** `sha256:9ea482f26144ee9a29f2fa3b9e99ae24bc84cdd31605a7d9c23c553e08c7f1fc`
· **Profile:** adversarial-v2-comparative on local-ollama · **Source of truth:**
`adversarial-cognition/docs/RESULTS-v2.md` · **Design:**
`docs/MARCIANA-ADVERSARIAL-v2.md` (issue #3)

v2 runs beside v1 — it never replaces it — and changes the method, not the
corpus: the same eighteen case intents, re-expressed through **authenticated
identities** (server-side registry, HMAC credentials, a negative-credential
probe before any case), split into two **tracks compared only within a track**.
Systems whose isolation was an adapter-chosen partition (`user_id`,
`group_id`, query-composed visibility) now *decline* authorization cases
rather than being credited with them — **coverage moved, correctness didn't.**

**Memory-store track** (storage APIs called directly):

| System | Coverage | Correct within coverage | v1 → v2 coverage note |
|--------|:--------:|:-----------------------:|------------------------|
| Marciana | 18/18 | 100% (18/18) | authenticated reference; probe passed |
| Akka + Fluree | 13/18 | 100% (13/13) | 16→13: query-composed visibility no longer credits isolation |
| Mem0 | 6/18 | 83% (5/6) | 9→6: `user_id` partition no longer credits isolation |
| Graphiti | 5/18 | 60% (3/5) | 8→5: `group_id` partition no longer credits isolation |
| Cognee | 6/18 | 50% (3/6) | dataset tiers are adapter-selected; declined |
| cognee-rs | 4/18 | 0% (0/4) | unchanged; still no determinism or input bounds |

**Agent-memory track** (one shared harness: `llama3.1:latest`, temperature 0,
seed 7, num_ctx 8192, max 6 turns — only the memory varies; ten of the
eighteen cases are expressible in the shared tool contract, uniformly for the
track):

| System | Coverage | Correct within coverage | Note |
|--------|:--------:|:-----------------------:|------|
| marciana-agent | 10/18 | 50% (5/10) | the reference under the shared loop |
| memfs-agent | 3/18 | 67% (2/3) | flat no-auth floor row |

The headline measurement v2 exists for: **the same governed reference scores
18/18 through its API and 5/10 through the shared agent loop.** The gap is the
model's contribution — failed abstention formatting, denials not reported as
empty answers, a forget the model executed incompletely — isolated from the
memory system for the first time. Letta appears in neither track this run:
Agent SDK 0.6.2 exposes its store only through Letta's own agent turns, which
would nest a second loop inside the harness — the row is declined with that
reason in the report, not faked. All nine hard gates zero; v1 results above
remain the frozen record of the v1 method.

Notes on this run. *Memory-store:* Akka+Fluree's stripped isolation is an
adapter posture, not a system verdict — its v1 adapter composed visibility
into query text, which v2 refuses to credit; a rework that pushes the policy
into Fluree's own server-side identity/policy surface would win those cases
back on merit. Mem0's one failure within its reduced coverage is the oversized
query; Graphiti keeps its v1 failures (token-order instability, unbounded
input); Cognee errors on the empty query and fails ordering and oversized
input; cognee-rs is unchanged. *Agent-memory:* marciana-agent's five failures
(`abstain-unknown`, `isolation-tenant`, `purpose-denial`, `forget-derived`,
`injection-contained`) are all loop costs, not store failures — the store
denied or filtered correctly and the model failed to report it in contract
form, or stopped short of completing the forget. That is a real, reproducible
(seeded) property of running memory behind a 8B-class loop — exactly what the
track measures. *Both letta rows* light up the moment Letta's SDK exposes the
passage store directly.

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

**Source of truth:** `catalog-bench@e7ca8c7/RESULTS.md`. Same four catalogs,
one shared MinIO, one ARM64 runner Docker, locked production builds, and
identical minimal commits. Six rounds rotated run order; round one conditioned
the stack, and the table reports medians of rounds two through six. Each run used
50 warmups, 1,000 sequential commits, then eight same-table writers for six
seconds.

| Raw order | Rank | Catalog | Valid rounds | Concurrent (8w) | Sequential | p50 | p99 | Conflicts | Error rate | Errors |
|----------:|:----:|---------|:------------:|----------------:|-----------:|----:|----:|----------:|-----------:|-------:|
| 1 | **DQ** | Nessie 0.108.4 | 0 / 5 | 190.0 /s | 312.3 /s | 2.986 ms | 5.602 ms | 81.00% | 0.366% | 97 |
| 2 | **1** | **LakeCat 0.3.0** | **5 / 5** | **153.0 /s** | **335.5 /s** | **2.697 ms** | **5.641 ms** | 85.42% | **0%** | **0** |
| 3 | **2** | Polaris 1.5.0 | **5 / 5** | 129.1 /s | 135.0 /s | 7.115 ms | 11.533 ms | 4.04% | **0%** | **0** |
| 4 | **3** | Gravitino 1.1.0 | **5 / 5** | 116.9 /s | 74.2 /s | 12.838 ms | 19.225 ms | 1.10% | **0%** | **0** |

The table is sorted by successful concurrent throughput. A numeric rank requires
zero request errors in every measured round, so Nessie's faster raw row remains
visible but is disqualified: all five measured rounds returned request-context
HTTP 500s, 97 in total. LakeCat is the valid concurrent and sequential leader.
All 24 MinIO object audits passed, and LakeCat's object growth exactly covered
every accepted commit in every round.

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
