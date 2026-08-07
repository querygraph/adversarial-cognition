# Appendix C — The catalog gates and cases

CATALOG-PROVENANCE-v1 counts safety failures in seven hard gates. A gate trips
only on a capability a catalog *claimed* and got wrong; an honestly-declared
unsupported capability never trips one. On the recorded run, every gate held at
zero for every executed catalog.

1. **`lost_update_accepted`** — a stale commit overwrote a newer one.
2. **`duplicate_commit_applied`** — an idempotent retry produced a second
   durable effect.
3. **`evidence_lost`** — audit, outbox, or lineage evidence was lost, or emitted
   without the commit that justifies it.
4. **`forged_proof_accepted`** — a tampered receipt verified.
5. **`unauthorized_scan_disclosed`** — a scan with a mismatched policy proof was
   accepted.
6. **`plaintext_in_evidence`** — evidence carried a raw location or secret.
7. **`non_deterministic_receipt`** — identical commits produced different
   receipts.

The seventeen cases, by capability:

| # | Case | Capability | The expectation |
|---|---|---|---|
| 1 | `commit-fresh` | commit | A fresh commit advances the pointer and yields a receipt |
| 2 | `cas-stale-rejected` | compare-and-swap | A commit asserting stale metadata is rejected |
| 3 | `cas-concurrent` | compare-and-swap | Two writers on one head: exactly one wins |
| 4 | `idempotent-retry` | idempotent-replay | A retried commit returns the stored receipt, no double-apply |
| 5 | `idempotent-across-restart` | idempotent-replay | Idempotency survives a restart |
| 6 | `audit-durable` | durable-audit | An accepted commit yields a durable audit event |
| 7 | `outbox-atomic-present` | atomic-outbox | An accepted commit stages an outbox event atomically |
| 8 | `outbox-absent-on-reject` | atomic-outbox | A rejected commit emits no outbox event |
| 9 | `replay-verifies` | replayable-proof | The commit receipt verifies offline |
| 10 | `replay-forged-rejected` | replayable-proof | A tampered receipt fails verification |
| 11 | `governed-scan-receipt` | governed-scan-proof | A scan carries a policy-bound authorization receipt |
| 12 | `governed-scan-mismatch-rejected` | governed-scan-proof | A scan receipt does not verify against a different policy |
| 13 | `receipt-chain-linked` | receipt-chain | A commit receipt links to its predecessor |
| 14 | `tombstone-covered` | tombstone-proof | A drop is covered by a tombstone receipt |
| 15 | `hash-only-audit` | hash-only-evidence | Evidence carries digests, never raw secrets |
| 16 | `lineage-emitted` | lineage-evidence | An accepted commit emits a lineage event |
| 17 | `restart-reproducible` | replayable-proof | The receipt still verifies after a restart |

The per-catalog coverage and gate counts for the latest run live in the
companion results report, regenerated whenever the suite runs and stamped with
the corpus digest. The durable finding, unchanged across runs, is that stock
Iceberg catalogs hold `commit` and `compare-and-swap` and decline the eleven
governance capabilities, while the governed reference holds all of them with
every gate at zero. Unity Catalog OSS is excluded on principle: its Iceberg REST
surface is read-only, with no commit path to make provable.
