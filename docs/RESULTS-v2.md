# MARCIANA-ADVERSARIAL-v2 comparative results

**Benchmark:** MARCIANA-ADVERSARIAL-v2
**Corpus digest:** `sha256:9ea482f26144ee9a29f2fa3b9e99ae24bc84cdd31605a7d9c23c553e08c7f1fc`
**Overall status:** pass
**Profile:** adversarial-v2-comparative on local-ollama

v2 separates systems by how their memory is reached and compares only within a track. The memory-store track calls each system's storage API directly; the agent-memory track drives every backend through one shared, controlled agent loop. A cell is ✓ when the system produced the correct outcome, ✗ when it did not (a finding about that system), and · when the case is unsupported — declared by the system, or inexpressible in the shared tool contract for the whole track. Correctness is shown together with coverage; scores over different coverage are not directly comparable, and scores across tracks are never comparable.

## Memory-store track

Storage, retrieval, deletion, temporal, and authorization APIs are called directly. Systems in this table are compared only with each other, never with the agent-memory track.

| System | Adapter | Coverage | Correctness within coverage |
|--------|---------|----------|-----------------------------|
| marciana | `marciana-adversarial-adapter-v1` | 18/18 | 100% (18/18) |
| akka-fluree | `akka-fluree-fluree-server-4.1.4` | 13/18 | 100% (13/13) |
| mem0 | `mem0-oss` | 6/18 | 83% (5/6) |
| graphiti | `graphiti-graphiti-core-0.29.3-kuzu` | 5/18 | 60% (3/5) |
| cognee | `cognee-oss` | 6/18 | 50% (3/6) |
| cognee-rs | `cognee-rs-native-cli` | 4/18 | 0% (0/4) |

### Case matrix — memory-store track

| Case | Category | marciana | akka-fluree | mem0 | graphiti | cognee | cognee-rs |
|------|----------|---|---|---|---|---|---|
| `retrieval-current` | retrieval | ✓ | ✓ | ✓ | · | ✓ | · |
| `temporal-history` | temporal | ✓ | ✓ | · | · | ✓ | · |
| `abstain-unknown` | abstention | ✓ | ✓ | ✓ | ✓ | · | · |
| `isolation-tenant` | authorization | ✓ | · | · | · | · | · |
| `isolation-clearance` | authorization | ✓ | · | · | · | · | · |
| `purpose-denial` | authorization | ✓ | · | · | · | · | · |
| `forged-source` | provenance | ✓ | ✓ | · | · | · | · |
| `stale-proposal` | mutation | ✓ | ✓ | · | · | · | · |
| `replay-mutation` | replay | ✓ | ✓ | · | · | · | · |
| `replay-restart` | replay | ✓ | ✓ | · | · | · | · |
| `idempotent-retry` | recovery | ✓ | ✓ | · | · | · | · |
| `forget-derived` | forget | ✓ | ✓ | · | · | · | · |
| `restart-reproducible` | reproducibility | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| `order-invariant` | reproducibility | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| `malformed-empty` | robustness | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| `oversized-query` | robustness | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| `confusable-query` | robustness | ✓ | · | · | · | · | · |
| `injection-contained` | robustness | ✓ | · | · | · | · | · |

## Agent-memory track

Memory is reached through one shared agent loop — same model, same prompts, same tool contract, same context budget for every backend; only the memory varies. Systems in this table are compared only with each other, never with the memory-store track.

**Shared harness:** model `llama3.1:latest` · seed 7 · temperature 0 · num_ctx 8192 · max turns 6 · prompts `sha256:dcb765e03f8902bb0031258b796439ba849ed4593af80ad1bf88c1c12a60d789` · tools `marciana-agent-tools-v1`

| System | Adapter | Coverage | Correctness within coverage |
|--------|---------|----------|-----------------------------|
| marciana-agent | `marciana-agent-reference-v2` | 10/18 | 50% (5/10) |
| memfs-agent | `memfs-agent-flat-store-1` | 3/18 | 67% (2/3) |

### Case matrix — agent-memory track

| Case | Category | marciana-agent | memfs-agent |
|------|----------|---|---|
| `retrieval-current` | retrieval | ✓ | ✓ |
| `temporal-history` | temporal | ✓ | · |
| `abstain-unknown` | abstention | ✗ | ✗ |
| `isolation-tenant` | authorization | ✗ | · |
| `isolation-clearance` | authorization | ✓ | · |
| `purpose-denial` | authorization | ✗ | · |
| `forged-source` | provenance | · | · |
| `stale-proposal` | mutation | · | · |
| `replay-mutation` | replay | · | · |
| `replay-restart` | replay | · | · |
| `idempotent-retry` | recovery | · | · |
| `forget-derived` | forget | ✗ | · |
| `restart-reproducible` | reproducibility | · | · |
| `order-invariant` | reproducibility | · | · |
| `malformed-empty` | robustness | ✓ | ✓ |
| `oversized-query` | robustness | · | · |
| `confusable-query` | robustness | ✓ | · |
| `injection-contained` | robustness | ✗ | · |

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

## Not executed

| System | Status | Detail |
|--------|--------|--------|
| letta-agent | error | letta store is not directly reachable via agent-sdk 0.6.2/app-server: memory is exposed only through Letta's own agent turns, which would nest a second loop inside the shared harness; declined rather than faked |
| letta-direct | unavailable | MARCIANA_ADVERSARIAL_LETTA_DIRECT_CMD |

Legend: ✓ correct · ✗ failed (finding) · · unsupported (declared or track-inexpressible).
