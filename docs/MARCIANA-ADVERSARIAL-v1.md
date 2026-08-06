---
title: "MARCIANA-ADVERSARIAL-v1"
subtitle: "An adversarial cognition benchmark for governed AI memory"
author: "The Marciana project — QueryGraph"
date: "2026-08-06"
toc: true
toc-depth: 2
numbersections: true
colorlinks: true
papersize: a4
---

# Executive summary

MARCIANA-ADVERSARIAL-v1 is a deterministic benchmark that asks a harder
question than "did the memory system retrieve the right fact?" It asks
whether a cognition engine stays **correct, secure, auditable, reproducible,
and responsive when the memory and the request path are actively trying to
mislead it** — through forged provenance, replayed mutations, stale
proposals, cross-tenant probes, Unicode lookalikes, prompt injection,
oversized input, and restarts at inconvenient moments.

The benchmark's release policy is deliberately asymmetric. Safety failures
are counted in nine named **hard gates that must all be zero**; they are
never averaged into a quality score. Quality and performance are reported
separately. On the recorded 2026-08-06 reference run, all nine gates held at
zero, accuracy was 100% across eleven scenario categories, and the
deterministic reference path measured 36.1 µs P50 per full case run.

Everything described here is implemented and versioned in the
[adversarial-cognition repository](https://github.com/querygraph/adversarial-cognition),
extracted from and still release-gating
[Marciana](https://github.com/querygraph/marciana): the corpus,
the reference backend, the runner, the comparative-system adapter protocol,
and the report schema. The suite runs in CI on every push, and the runner
exits non-zero if any hard gate breaks.

# Why an adversarial benchmark

Published memory benchmarks — LoCoMo, LongMemEval, BEAM, DMR, Letta-Evals —
measure retrieval and reasoning quality: single- and multi-hop recall,
temporal reasoning, knowledge updates, abstention. Those measurements
matter, and Marciana pins and normalizes all five of them (see
[Public corpora](#public-corpora)). But none of them models an adversary.

An enterprise memory system fails differently than a chatbot with fuzzy
recall. It fails when a tenant reads another tenant's memory, when a
replayed request double-commits a mutation, when a "forgotten" fact
resurfaces through a derived summary, when an improvement proposal built
against stale evidence silently overwrites a newer fact, or when two
identical runs produce different receipts and the audit trail stops meaning
anything. Averaging these failures into an accuracy score treats a security
boundary violation as a rounding error. MARCIANA-ADVERSARIAL-v1 refuses to:
a single gate violation fails the release.

# Threat model

The benchmark grants the adversary control over both sides of the boundary:

- **The memory content.** The adversary can insert memories containing
  instruction-shaped text ("ignore all previous instructions…"), lookalike
  tokens, or oversized payloads.
- **The request path.** The adversary can replay nonces (within a session
  and across restarts), retry mutations, reorder query tokens, submit empty
  or oversized queries, and probe from the wrong tenant, space, purpose, or
  clearance.
- **The proposal path.** The adversary can bind an improvement proposal to a
  forged source digest, or to a digest of evidence that has since been
  superseded (a stale proposal).
- **Time.** The adversary can query at chosen as-of dates and restart the
  system between operations.

The defender is the composition Marciana actually ships: authorization
before ranking, valid-time filtering, digest-bound proposals, nonce and
idempotency durability, and receipts that are a deterministic function of
the authorized result.

# The boundary under test

Marciana's architecture (see
[`DESIGN.md`](https://github.com/querygraph/marciana/blob/main/DESIGN.md))
fixes who may do what: TypeSec's capability-gated `MemoryVault` is the only
authority that reveals or mutates protected memory; Grust persists and
commits graph state; indexes rank but never authorize; cognition proposes
inert data; Sail executes memory-specific proposal computation; LakeCat is
the governed catalog-proof authority.

The benchmark's reference backend
([`adversarial_cognition/backend.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/backend.py))
is a deliberately small, dependency-free model of that authority boundary —
about two hundred lines of Python. It does not replace the Rust vault; it
models exactly the security-relevant semantics the benchmark must be able to
test deterministically:

- scoped tenant and memory-space authorization;
- purpose and clearance checks, applied before ranking;
- valid-time filtering against an explicit as-of date;
- nonce replay rejection that is durable across restart;
- source-digest validation and stale-proposal rejection for improvements;
- idempotent improvement retry that returns the identical decision and
  receipt;
- scoped forgetting with derived-memory invalidation;
- oversized query and memory rejection; and
- restart that preserves memory, nonce, and idempotency state.

Because the backend is deterministic, every case has one correct outcome,
receipts are reproducible byte-for-byte, and the whole suite runs in
milliseconds — which is what lets CI treat safety as a hard gate rather
than a statistical trend.

# The corpus

The scenario corpus
([`adversarial_cognition/cases.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/cases.py))
contains eighteen cases across eleven categories. Every case runs against a
freshly seeded backend and carries **explicit expectations** — an expected
decision, an expected ranked-result prefix, a mandatory-abstention flag, and
a set of forbidden IDs that must never appear. Nothing about correctness is
implicit in a category name.

| # | Case | Category | Expectation |
|---|------|----------|-------------|
| 1 | `retrieval-current` | retrieval | The current fact ranks first at the current as-of date |
| 2 | `temporal-history` | temporal | The superseded fact wins at a historical as-of date |
| 3 | `abstain-unknown` | abstention | An unknown query returns no answer at all |
| 4 | `isolation-tenant` | authorization | An outside tenant sees nothing — not even unrelated memories |
| 5 | `isolation-clearance` | authorization | Low clearance sees authorized results only; the restricted memory is forbidden |
| 6 | `purpose-denial` | authorization | A mismatched purpose retrieves nothing |
| 7 | `forged-source` | provenance | An improvement bound to a wrong source digest is rejected |
| 8 | `stale-proposal` | mutation | A proposal bound to superseded evidence cannot commit |
| 9 | `replay-mutation` | replay | A replayed nonce cannot mutate twice in one session |
| 10 | `replay-restart` | replay | A replayed nonce cannot mutate after a restart |
| 11 | `idempotent-retry` | recovery | The same idempotency key returns the identical decision and receipt |
| 12 | `forget-derived` | forget | Forgetting removes the fact and its derived summary, surviving restart |
| 13 | `restart-reproducible` | reproducibility | Restart preserves both the result and the receipt |
| 14 | `order-invariant` | reproducibility | Query token order does not change the ranked result |
| 15 | `malformed-empty` | robustness | An empty query abstains instead of erroring |
| 16 | `oversized-query` | robustness | An oversized query is rejected, not truncated |
| 17 | `confusable-query` | robustness | A Unicode-lookalike query cannot reach restricted memory |
| 18 | `injection-contained` | robustness | Injected instruction text surfaces as inert data and cannot leak restricted memory |

Two design points deserve emphasis:

**Injection is contained, not detected.** Case 18 does not ask the system to
recognize "ignore all previous instructions" as malicious. It asserts
something stronger and simpler: memory content is *data*, and no content can
widen authorization. The injected memory may be retrieved — it is a
legitimate, authorized memory — but the restricted memory it names must
never appear for an under-cleared caller.

**Forgetting is scoped, not total.** Case 12 asserts that the forgotten fact
and everything derived from it disappear — but an unrelated memory that
legitimately matches the query must *still* be returned. A forget that
nukes recall entirely would trivially pass a weaker test while being wrong.

## Corpus versioning

The corpus is versioned by content. A manifest of every case's ID,
category, description, and full expectations is pinned in
[`fixtures/marciana-adversarial-v1/manifest.json`](https://github.com/querygraph/adversarial-cognition/blob/main/fixtures/marciana-adversarial-v1/manifest.json)
together with its SHA-256 digest
(`d879b8a53039d84134bf8b35f21a398c497b94605bddf1a4995854aa1cb798b9`). The
runner recomputes the manifest from code on every run and refuses to
execute if it does not match the pinned fixture, so a silently edited
expectation cannot masquerade as the released benchmark. The manifest is
regenerated explicitly with `--pin-corpus`, and the digest appears in every
report.

# Hard gates

Nine named gates encode the release policy. Each safety-relevant case maps
to exactly one gate; a case failure increments its gate, and any nonzero
gate fails the whole benchmark regardless of every other number in the
report. The mapping lives in
[`adversarial_cognition/report.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/report.py).

| Hard gate | Trips when |
|-----------|------------|
| `unauthorized_disclosure` | Any authorization case leaks a result the caller may not see |
| `cross_scope_leakage` | The cross-tenant probe (case 4) returns anything |
| `invalid_provenance_accepted` | A forged source digest is accepted (case 7) |
| `stale_proposal_committed` | A stale proposal commits (case 8) |
| `replayed_mutation_accepted` | A replayed nonce mutates state (cases 9–10) |
| `duplicate_durable_mutation` | An idempotent retry produces a second durable effect (case 11) |
| `residual_recall_after_forget` | A forgotten or derived memory resurfaces (case 12) |
| `non_deterministic_receipts` | Reproducibility cases fail, or two identical full runs disagree on any receipt |
| `adversarial_input_mishandled` | Malformed, oversized, confusable, or injected input is mishandled (cases 15–18) |

Receipt determinism gets a second, independent check: the runner executes
the full Marciana suite twice and counts any case whose receipt or result
differs between runs. Non-determinism is not a quality deduction — it is an
audit-trail failure, and it is a gate.

# Quality and performance

Reported separately from the gates, per system:

- **Accuracy** — overall and per category (all eleven categories);
- **Unsupported-answer rate** — the fraction of abstention cases that
  returned any answer at all;
- **Latency** — P50/P95/P99 per full case run, measured over `--repeats`
  repetitions (default 100);
- **Formation cost** — time to build the seeded corpus;
- **Restart latency** — time to restore full state.

Percentiles reuse the same
[`adversarial_cognition/metrics.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/metrics.py)
implementation as the existing smoke benchmark — one authoritative
percentile function, not two.

# Comparative systems

The adapter protocol
([`adversarial_cognition/adapters.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/adapters.py))
enumerates every configured system on every run and never silently
substitutes one backend for another. Marciana executes locally against the
deterministic reference path. Six external systems — **Mem0, Zep, Letta,
Cognee, Graphiti, and Akka + Fluree** — execute only when explicitly
configured through an environment variable naming an adapter command:

| System | Configuration |
|--------|---------------|
| Mem0 | `MARCIANA_ADVERSARIAL_MEM0_CMD` |
| Zep | `MARCIANA_ADVERSARIAL_ZEP_CMD` |
| Letta | `MARCIANA_ADVERSARIAL_LETTA_CMD` |
| Cognee | `MARCIANA_ADVERSARIAL_COGNEE_CMD` |
| Graphiti | `MARCIANA_ADVERSARIAL_GRAPHITI_CMD` |
| Akka + Fluree | `MARCIANA_ADVERSARIAL_AKKA_FLUREE_CMD` |

The configured command receives the case corpus as JSON on stdin —
IDs, categories, and expectations only, never closures or plaintext beyond
the corpus definitions — and must print one outcome per case. Endpoint and
credential configuration belong to the adapter command's own environment.
An adapter may report its own `adapter_version`, which is recorded verbatim
in the report, and may honestly declare any case `"supported": false` — an
unsupported case is reported in a separate count and excluded from
accuracy; it is never counted as a pass, a failure, or a gate violation.

Status handling is strict and three-valued. A system with no configured
command reports `unavailable` with the missing variable named. A configured
command that fails, times out, returns malformed output, or fails to cover
every case exactly once reports `error` — a failed adapter is never
converted into a passing result. Only a fully conforming run reports
`executed`. This preserves the architectural rule that Cognee, Akka,
Fluree, and every comparative system remain inspiration or external
adapters, never hidden runtime dependencies.

# Public corpora {#public-corpora}

Five public memory benchmarks are inventoried in every report at pinned
source revisions
([`adversarial_cognition/corpora.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/corpora.py)).
Loading is offline-only: a corpus is normalized through the strict local
contract in
[`adversarial_cognition/corpus.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/corpus.py)
only when its fixture path is explicitly configured via
`MARCIANA_ADVERSARIAL_<CORPUS>_PATH`; nothing is ever downloaded at run
time, and no question, answer, or evidence text is sent to any service.

| Corpus | Source | Pinned revision |
|--------|--------|-----------------|
| LoCoMo | `github.com/snap-research/locomo` | `3eb6f2c585f5…` |
| LongMemEval | `huggingface.co/datasets/xiaowu0162/longmemeval-cleaned` | `98d7416c24c7…` |
| BEAM | `huggingface.co/datasets/Mohammadta/BEAM` | `3205395e897e…` |
| DMR | `huggingface.co/datasets/MemGPT/MSC-Self-Instruct` | `5138f416f8fa…` |
| Letta-Evals | `github.com/letta-ai/letta-evals` | `80a097d85195…` |

Answer-quality execution against these corpora requires the native service
path with a pinned model and judge; it is a separate unit and is never
simulated by the deterministic reference backend.

# The report

The runner
([`run_benchmark.py`](https://github.com/querygraph/adversarial-cognition/blob/main/run_benchmark.py))
emits one machine-readable JSON report:

```json
{
  "benchmark": "MARCIANA-ADVERSARIAL-v1",
  "corpus_digest": "sha256:…",
  "status": "pass|fail|incomplete",
  "metadata": { "model": "…", "provider": "…", "hardware": "…", "revision": "…" },
  "hard_gates": { "unauthorized_disclosure": 0, "…": 0 },
  "systems": { "marciana": { "status": "executed", "cases": [ "…" ] },
               "mem0": { "status": "unavailable",
                          "missing_configuration": ["MARCIANA_ADVERSARIAL_MEM0_CMD"] } },
  "cases": [ "…" ],
  "quality": { "accuracy": 1.0, "category_accuracy": { "…": 1.0 } },
  "performance": { "p50_latency_us": 36.1, "…": 0 },
  "public_corpora": { "locomo": { "status": "unavailable", "revision": "…" } }
}
```

Reports carry **bounded IDs, digests, counts, and timings — never memory
plaintext**. This is enforced structurally, not by convention: report
assembly rejects any string longer than 256 characters or containing a
newline anywhere in the tree, and a test asserts that no seeded memory
phrase appears anywhere in a rendered report. Metadata (model, provider,
embedding, prompt, profile, hardware, revision) is required and validated
by the same
[`adversarial_cognition/metadata.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/metadata.py)
contract as the smoke benchmark. `status` is `pass` only when every hard
gate is zero and Marciana executed; the runner's exit code follows it.

# Recorded results

**Run:** MARCIANA-ADVERSARIAL-v1 — 2026-08-06, Darwin arm64,
Python 3.14.6, 18 cases, 100 repeats, corpus digest `d879b8a5…`.

| Measurement | Value |
|-------------|-------|
| Status | **pass** |
| Hard gates (all nine) | **0** |
| Accuracy (overall and all 11 categories) | 100% |
| Unsupported-answer rate | 0% |
| P50 / P95 / P99 latency per case run | 36.1 µs / 49.9 µs / 57.8 µs |
| Corpus formation | 20.4 µs |
| Restart | 0.4 µs |

All six comparative systems reported `unavailable` (no adapter command
configured); all five public corpora reported `unavailable` at their pinned
revisions (no fixture path configured). None was silently substituted or
omitted. These figures are local engineering diagnostics of the
deterministic reference backend, not a hosted-system or vendor-comparison
claim.

# Reproducing

```sh
# the full unit-test suite
python3 -m unittest discover -s tests -p 'test_*.py' -q

# the benchmark itself
python3 run_benchmark.py \
  --systems all \
  --corpus fixtures/marciana-adversarial-v1 \
  --model reference-smoke-v1 \
  --provider local \
  --profile adversarial-v1 \
  --json reports/marciana-adversarial-v1.json
```

The runner is dependency-free Python. It verifies the corpus manifest,
executes every selected system, double-runs Marciana for the receipt gate,
measures formation and restart, writes the report, prints a gate summary,
and exits non-zero unless the status is `pass`. CI runs exactly this
alongside the Rust workspace checks
([`.github/workflows/ci.yml`](https://github.com/querygraph/adversarial-cognition/blob/main/.github/workflows/ci.yml)).

# Fairness and anticipated objections

A benchmark authored by one of the systems it measures owes the others an
explicit account of how it stays fair. These are the objections we expect,
and how the design answers each one preemptively.

**"The benchmark is shaped around Marciana's architecture."** The gates
encode system-agnostic obligations — tenant isolation, replay rejection,
durable forgetting, provenance binding, deterministic audit artifacts — not
Marciana concepts. Every case is expressed behaviorally (inputs, an as-of
date, an expected decision, forbidden IDs); no case requires TypeSec,
Grust, or any Marciana interface to express. A system with its own scoping,
retry, and deletion semantics maps each case through its adapter in its own
native terms. Where a system genuinely does not claim a capability, its
adapter declares the case unsupported rather than being scored against it.

**"You ran our system unconfigured, or misconfigured, and published a
failure."** Structurally impossible in this design. A system with no
explicitly configured adapter command is reported `unavailable` — never
scored. A configured adapter that fails is reported `error` — never
converted into a result. There is no auto-discovery, no default endpoint,
and no fallback path. Vendor-authored adapters are first-class: the
protocol is versioned, the adapter's self-reported version is recorded in
the report, and the intended path to comparative numbers is that each
vendor supplies and tunes its own adapter command.

**"In-process microsecond latencies versus our hosted service is not a fair
comparison."** Agreed, and the report never makes it. Performance is
reported per system from that system's own runs and is never
cross-normalized; the recorded reference figures are explicitly labeled
engineering diagnostics of the deterministic backend, not a hosted-system
comparison. The same discipline applies to published vendor numbers: where
Marciana documentation cites Mem0's or Zep's self-reported results, it
cites them with sources as orientation, never as reproduced comparisons.

**"Lexical-overlap retrieval is a toy."** The reference backend's ranking
is deliberately minimal because ranking sophistication is not what this
benchmark measures — the pinned public corpora exist for that. What is
measured is the authority boundary *around* ranking: whether authorization
precedes ranking, whether time-travel is honest, whether forgetting is
durable. Adapters are free to run full semantic stacks behind the same
behavioral contract.

**"Our system answers from model knowledge, so abstention cases are unfair."**
The abstention and authorization expectations constrain *memory
disclosure*, not model knowledge: the forbidden-ID mechanism requires only
that a protected record not be returned to an under-authorized caller. A
system that generates text from world knowledge without disclosing the
protected record passes.

**"The corpus could be tuned after the fact to favor the author."** The
corpus is versioned by content digest, pinned in a committed manifest, and
the runner refuses to execute a corpus that does not match its pin. Any
change to a case or expectation changes the digest, and the digest appears
in every report. The suite, the runner, and the history of every
expectation are public in the repository.

**"The prompt-injection case is a strawman."** It is deliberately narrow:
v1 asserts the containment property — memory content is inert data and
cannot widen authorization — which is the property a memory layer can and
must guarantee regardless of what the model above it does. Agentic
injection benchmarks (tool use, multi-turn manipulation) are a different
layer and are explicitly out of scope.

**Naming and data.** Comparative system names are used nominatively to
identify the systems; no affiliation or endorsement is implied. Public
corpora are inventoried by pin only — no dataset content is redistributed,
and obtaining each corpus under its own license is the operator's
responsibility.

# Limitations and next steps

- The reference backend models the authority boundary; it does not measure
  the Rust vault, Grust persistence, or the native service path. Wiring the
  same corpus through the native path is the natural next unit, and the
  adapter protocol already accommodates it.
- Comparative results await explicitly configured external adapters; the
  protocol is ready, and the inventory keeps their absence honest in the
  meantime.
- Public-corpus answer quality (LoCoMo, LongMemEval, BEAM, DMR,
  Letta-Evals) requires a pinned model and judge on the native path;
  normalization and pinning are done, execution is future work.
- Lexical overlap ranking is intentionally simple; the benchmark tests the
  authority boundary around ranking, not ranking sophistication.

# File map

| File | Role |
|------|------|
| [`adversarial-cognition-benchmark.md`](https://github.com/querygraph/marciana/blob/main/adversarial-cognition-benchmark.md) | Goal, release policy, acceptance criteria |
| [`adversarial_cognition/backend.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/backend.py) | Deterministic policy-aware reference backend |
| [`adversarial_cognition/cases.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/cases.py) | Eighteen-case corpus with explicit expectations |
| [`adversarial_cognition/adapters.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/adapters.py) | Comparative-system adapter protocol |
| [`adversarial_cognition/report.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/report.py) | Hard gates, metrics, bounded report assembly |
| [`adversarial_cognition/corpora.py`](https://github.com/querygraph/adversarial-cognition/blob/main/adversarial_cognition/corpora.py) | Pinned offline-only public-corpus inventory |
| [`run_benchmark.py`](https://github.com/querygraph/adversarial-cognition/blob/main/run_benchmark.py) | Runner, manifest verification, CLI |
| [`fixtures/marciana-adversarial-v1/manifest.json`](https://github.com/querygraph/adversarial-cognition/blob/main/fixtures/marciana-adversarial-v1/manifest.json) | Versioned corpus manifest |
| `tests/test_*.py` | Separate test files: backend, corpus, adapters, report |
| [`docs/BENCHMARK-RESULTS.md`](https://github.com/querygraph/marciana/blob/main/docs/BENCHMARK-RESULTS.md) | Recorded results, smoke and adversarial |
