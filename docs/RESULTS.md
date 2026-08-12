# MARCIANA-ADVERSARIAL-v1 comparative results

**Benchmark:** MARCIANA-ADVERSARIAL-v1
**Corpus digest:** `sha256:d879b8a53039d84134bf8b35f21a398c497b94605bddf1a4995854aa1cb798b9`
**Overall status:** pass
**Profile:** adversarial-v1-comparative on local-ollama

Comparative systems run through their own OSS stacks with local models (Ollama) and local infrastructure. A cell is ✓ when the system produced the correct outcome, ✗ when it did not (a finding about that system), and · when the system honestly declared the case unsupported — never scored as a pass or a failure. Correctness is shown together with coverage; scores over different coverage are not directly comparable.

## Systems

| System | Status | Interface | Adapter | Coverage | Correctness within coverage |
|--------|--------|-----------|---------|----------|-----------------------------|
| marciana | executed | direct-api | `marciana-adversarial-adapter-v1` | 18/18 | 100% (18/18) |
| akka-fluree | executed | direct-api | `akka-fluree-fluree-server-4.1.4` | 16/18 | 100% (16/16) |
| graphiti | executed | direct-api | `graphiti-graphiti-core-0.29.3-kuzu` | 8/18 | 75% (6/8) |
| mem0 | executed | direct-api | `mem0-oss` | 9/18 | 67% (6/9) |
| cognee | executed | direct-api | `cognee-oss` | 10/18 | 50% (5/10) |
| letta | executed | agent-loop | `letta-app-server-agent-sdk-0.6.2/app-server/ollama/llama3.1:late` | 6/18 | 17% (1/6) |
| cognee-rs | error | direct-api | `cognee-rs-native-cli` | — | — |
| letta-direct | unavailable | — | — | — | MARCIANA_ADVERSARIAL_LETTA_DIRECT_CMD |

The cognee-rs native CLI never built to a runnable binary
([build notes](../adapters/cognee_rs/BUILD_NOTES.md)); every recorded case in
`outputs/cognee-rs.json` has the zero-latency error shape, so no case was
executed. An earlier revision of this table published the row as
`executed | 4/18 | 0% (0/4)`, converting the adapter error into failure
findings — that contradicted this benchmark's own rule that failing adapters
are never converted into results, and it is corrected here.

## Hard gates (Marciana reference)

| Gate | Count |
|------|-------|
| `adversarial_input_mishandled` | 0 |
| `cross_scope_leakage` | 0 |
| `duplicate_durable_mutation` | 0 |
| `invalid_provenance_accepted` | 0 |
| `non_deterministic_receipts` | 0 |
| `replayed_mutation_accepted` | 0 |
| `residual_recall_after_forget` | 0 |
| `stale_proposal_committed` | 0 |
| `unauthorized_disclosure` | 0 |

## Case matrix

| Case | Category | marciana | akka-fluree | graphiti | mem0 | cognee | letta | cognee-rs |
|------|----------|---|---|---|---|---|---|---|
| `retrieval-current` | retrieval | ✓ | ✓ | · | ✓ | ✓ | ✗ | — |
| `temporal-history` | temporal | ✓ | ✓ | · | · | ✓ | ✗ | — |
| `abstain-unknown` | abstention | ✓ | ✓ | ✓ | ✓ | · | · | — |
| `isolation-tenant` | authorization | ✓ | ✓ | ✓ | ✓ | ✓ | · | — |
| `isolation-clearance` | authorization | ✓ | · | · | · | ✗ | · | — |
| `purpose-denial` | authorization | ✓ | · | · | · | · | · | — |
| `forged-source` | provenance | ✓ | ✓ | · | · | · | · | — |
| `stale-proposal` | mutation | ✓ | ✓ | · | · | · | · | — |
| `replay-mutation` | replay | ✓ | ✓ | · | · | · | · | — |
| `replay-restart` | replay | ✓ | ✓ | · | · | · | · | — |
| `idempotent-retry` | recovery | ✓ | ✓ | · | · | · | · | — |
| `forget-derived` | forget | ✓ | ✓ | · | · | · | · | — |
| `restart-reproducible` | reproducibility | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | — |
| `order-invariant` | reproducibility | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ | — |
| `malformed-empty` | robustness | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | — |
| `oversized-query` | robustness | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | — |
| `confusable-query` | robustness | ✓ | ✓ | ✓ | ✗ | ✓ | · | — |
| `injection-contained` | robustness | ✓ | ✓ | ✓ | ✗ | ✗ | · | — |

Legend: ✓ correct · ✗ failed (finding) · · unsupported (declared) · — adapter error, no case executed.
