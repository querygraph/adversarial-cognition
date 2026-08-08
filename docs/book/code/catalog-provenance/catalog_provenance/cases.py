"""The CATALOG-PROVENANCE-v1 case corpus, run against the reference catalog.

Each case exercises one provable-transaction property behaviorally, with an
explicit expected outcome. The reference catalog must pass every case; that is
the CI gate and the executable definition of "provable transaction."

Capabilities name what a catalog *enforces*; a comparison catalog that does not
claim a capability declares the case unsupported rather than being scored on
it. Gates are the zero-tolerance safety properties: any gate failure fails the
release, regardless of every other number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .backend import ReferenceCatalog

CORPUS_VERSION = "catalog-provenance-v1"

# What a catalog may claim to enforce.
CAPABILITIES = (
    "commit",              # accept an Iceberg table commit and advance the pointer
    "compare-and-swap",    # reject a commit whose expected metadata is stale
    "idempotent-replay",   # a retried commit returns the stored result, no double-apply
    "durable-audit",       # every accepted commit yields a durable audit event
    "atomic-outbox",       # lineage/graph evidence is staged atomically with the commit
    "replayable-proof",    # the commit receipt verifies offline and survives restart
    "governed-scan-proof", # a scan carries a policy-digest-bound authorization receipt
    "receipt-chain",       # receipts link to their predecessor / upsert head
    "tombstone-proof",     # a drop is covered by a tombstone receipt
    "hash-only-evidence",  # evidence carries digests, never plaintext locations or secrets
    "lineage-evidence",    # an accepted commit emits a lineage event
)

# Safety gates: each maps to the case(s) whose failure trips it.
GATES = (
    "lost_update_accepted",       # a stale commit overwrote a newer one
    "duplicate_commit_applied",   # an idempotent retry produced a second effect
    "evidence_lost",              # audit/outbox/lineage evidence lost, or emitted without its commit
    "forged_proof_accepted",      # a tampered receipt verified
    "unauthorized_scan_disclosed",# a scan with mismatched policy proof was accepted
    "plaintext_in_evidence",      # evidence carried a raw location or secret
    "non_deterministic_receipt",  # identical commits produced different receipts
)


@dataclass(frozen=True)
class Case:
    case_id: str
    category: str
    capability: str
    description: str
    run: Callable[[ReferenceCatalog], bool] = field(compare=False)
    gate: str = ""  # the safety gate this case guards, if any


def _seeded() -> ReferenceCatalog:
    cat = ReferenceCatalog()
    cat.create("sales.events", "did:key:operator")
    return cat


POLICY = "read allowed for purpose analytics"
SECRET = "s3://warehouse/secret-location/AKIAEXAMPLE"


def cases() -> tuple[Case, ...]:
    def commit_fresh(cat: ReferenceCatalog) -> bool:
        before = cat.pointer("sales.events")
        out = cat.commit("sales.events", before, "add-snapshot", "did:key:operator",
                         POLICY, "n1", "job-1")
        return out.ok and out.receipt is not None and cat.pointer("sales.events") != before

    def cas_stale_rejected(cat: ReferenceCatalog) -> bool:
        head = cat.pointer("sales.events")
        cat.commit("sales.events", head, "u1", "did:key:operator", POLICY, "n1", "job-1")
        # Second writer still asserts the old head → must be rejected.
        out = cat.commit("sales.events", head, "u2", "did:key:operator", POLICY, "n2", "job-2")
        return (not out.ok) and out.error == "stale-metadata"

    def cas_concurrent(cat: ReferenceCatalog) -> bool:
        head = cat.pointer("sales.events")
        a = cat.commit("sales.events", head, "a", "did:key:w1", POLICY, "na", "job-a")
        b = cat.commit("sales.events", head, "b", "did:key:w2", POLICY, "nb", "job-b")
        # Exactly one wins; the other is rejected and left no effect.
        return a.ok and not b.ok

    def idempotent_retry(cat: ReferenceCatalog) -> bool:
        head = cat.pointer("sales.events")
        first = cat.commit("sales.events", head, "u", "did:key:operator", POLICY, "n1", "job-k")
        after_first = cat.pointer("sales.events")
        # Same key, retried — returns the identical receipt and does not advance again.
        second = cat.commit("sales.events", head, "u", "did:key:operator", POLICY, "n2", "job-k")
        return (first.ok and second.ok
                and first.receipt == second.receipt
                and cat.pointer("sales.events") == after_first)

    def durable_audit(cat: ReferenceCatalog) -> bool:
        n = len(cat.audit)
        out = cat.commit("sales.events", cat.pointer("sales.events"), "u",
                         "did:key:operator", POLICY, "n1", "job-1")
        return out.ok and out.audit_present and len(cat.audit) == n + 1

    def outbox_atomic_present(cat: ReferenceCatalog) -> bool:
        n = len(cat.outbox)
        out = cat.commit("sales.events", cat.pointer("sales.events"), "u",
                         "did:key:operator", POLICY, "n1", "job-1")
        return out.ok and out.outbox_present and len(cat.outbox) == n + 1

    def outbox_absent_on_reject(cat: ReferenceCatalog) -> bool:
        head = cat.pointer("sales.events")
        cat.commit("sales.events", head, "u1", "did:key:operator", POLICY, "n1", "job-1")
        n = len(cat.outbox)
        # A rejected (stale) commit must emit NO outbox event.
        rej = cat.commit("sales.events", head, "u2", "did:key:operator", POLICY, "n2", "job-2")
        return (not rej.ok) and len(cat.outbox) == n

    def replay_verifies(cat: ReferenceCatalog) -> bool:
        out = cat.commit("sales.events", cat.pointer("sales.events"), "u",
                         "did:key:operator", POLICY, "n1", "job-1")
        return out.ok and cat.replay(out.receipt)

    def replay_forged_rejected(cat: ReferenceCatalog) -> bool:
        out = cat.commit("sales.events", cat.pointer("sales.events"), "u",
                         "did:key:operator", POLICY, "n1", "job-1")
        from dataclasses import replace as _r
        forged = _r(out.receipt, response_hash="sha256:" + "0" * 64)
        # A tampered receipt must fail offline verification.
        return out.ok and not forged.verifies() and not cat.replay(forged)

    def governed_scan_receipt(cat: ReferenceCatalog) -> bool:
        cat.commit("sales.events", cat.pointer("sales.events"), "u",
                   "did:key:operator", POLICY, "n1", "job-1")
        out = cat.scan("sales.events", "did:key:operator", POLICY)
        from .backend import policy_digest
        return (out.ok and out.scan_receipt is not None
                and out.scan_receipt.verifies((policy_digest(POLICY),)))

    def governed_scan_mismatch_rejected(cat: ReferenceCatalog) -> bool:
        out = cat.scan("sales.events", "did:key:operator", POLICY)
        from .backend import policy_digest
        # A scan receipt planned under POLICY must not verify against a different policy.
        return out.ok and not out.scan_receipt.verifies((policy_digest("some other policy"),))

    def receipt_chain_linked(cat: ReferenceCatalog) -> bool:
        head = cat.pointer("sales.events")
        first = cat.commit("sales.events", head, "u1", "did:key:operator", POLICY, "n1", "job-1")
        second = cat.commit("sales.events", cat.pointer("sales.events"), "u2",
                            "did:key:operator", POLICY, "n2", "job-2")
        return (first.ok and second.ok
                and second.receipt.prev_receipt == first.receipt.receipt_hash)

    def tombstone_covered(cat: ReferenceCatalog) -> bool:
        cat.commit("sales.events", cat.pointer("sales.events"), "u",
                   "did:key:operator", POLICY, "n1", "job-1")
        out = cat.tombstone("sales.events", "did:key:operator", POLICY, "nd")
        return out.ok and out.receipt is not None and out.receipt.op == "tombstone"

    def hash_only_audit(cat: ReferenceCatalog) -> bool:
        out = cat.commit("sales.events", cat.pointer("sales.events"), SECRET,
                         "did:key:operator", POLICY, "n1", "job-1")
        # No audit/outbox/lineage/receipt evidence may contain the raw secret text.
        blobs = cat.audit + cat.outbox + cat.lineage + [r.new_metadata for r in cat.receipts.values()]
        return out.ok and all("AKIA" not in b and "secret-location" not in b for b in blobs)

    def lineage_emitted(cat: ReferenceCatalog) -> bool:
        n = len(cat.lineage)
        out = cat.commit("sales.events", cat.pointer("sales.events"), "u",
                         "did:key:operator", POLICY, "n1", "job-1")
        return out.ok and out.lineage_present and len(cat.lineage) == n + 1

    def restart_reproducible(cat: ReferenceCatalog) -> bool:
        out = cat.commit("sales.events", cat.pointer("sales.events"), "u",
                         "did:key:operator", POLICY, "n1", "job-1")
        # The receipt still verifies against the durable state after a restart.
        return out.ok and cat.restart().replay(out.receipt)

    def idempotent_across_restart(cat: ReferenceCatalog) -> bool:
        head = cat.pointer("sales.events")
        first = cat.commit("sales.events", head, "u", "did:key:operator", POLICY, "n1", "job-k")
        restarted = cat.restart()
        # The idempotency record is durable: the retry after restart still dedupes.
        second = restarted.commit("sales.events", head, "u", "did:key:operator", POLICY, "n2", "job-k")
        return first.ok and second.ok and first.receipt == second.receipt

    return (
        Case("commit-fresh", "commit", "commit", "a fresh commit advances the pointer and yields a receipt", commit_fresh),
        Case("cas-stale-rejected", "concurrency", "compare-and-swap", "a commit asserting stale metadata is rejected", cas_stale_rejected, "lost_update_accepted"),
        Case("cas-concurrent", "concurrency", "compare-and-swap", "two writers on one head: exactly one wins", cas_concurrent, "lost_update_accepted"),
        Case("idempotent-retry", "idempotency", "idempotent-replay", "a retried commit returns the stored receipt, no double-apply", idempotent_retry, "duplicate_commit_applied"),
        Case("idempotent-across-restart", "idempotency", "idempotent-replay", "idempotency survives a restart", idempotent_across_restart, "duplicate_commit_applied"),
        Case("audit-durable", "audit", "durable-audit", "an accepted commit yields a durable audit event", durable_audit, "evidence_lost"),
        Case("outbox-atomic-present", "outbox", "atomic-outbox", "an accepted commit stages an outbox event atomically", outbox_atomic_present, "evidence_lost"),
        Case("outbox-absent-on-reject", "outbox", "atomic-outbox", "a rejected commit emits no outbox event", outbox_absent_on_reject, "evidence_lost"),
        Case("replay-verifies", "proof", "replayable-proof", "the commit receipt verifies offline", replay_verifies, "forged_proof_accepted"),
        Case("replay-forged-rejected", "proof", "replayable-proof", "a tampered receipt fails verification", replay_forged_rejected, "forged_proof_accepted"),
        Case("governed-scan-receipt", "governed-read", "governed-scan-proof", "a scan carries a policy-bound authorization receipt", governed_scan_receipt, "unauthorized_scan_disclosed"),
        Case("governed-scan-mismatch-rejected", "governed-read", "governed-scan-proof", "a scan receipt does not verify against a different policy", governed_scan_mismatch_rejected, "unauthorized_scan_disclosed"),
        Case("receipt-chain-linked", "chain", "receipt-chain", "a commit receipt links to its predecessor", receipt_chain_linked),
        Case("tombstone-covered", "tombstone", "tombstone-proof", "a drop is covered by a tombstone receipt", tombstone_covered),
        Case("hash-only-audit", "redaction", "hash-only-evidence", "evidence carries digests, never raw secrets", hash_only_audit, "plaintext_in_evidence"),
        Case("lineage-emitted", "lineage", "lineage-evidence", "an accepted commit emits a lineage event", lineage_emitted, "evidence_lost"),
        Case("restart-reproducible", "proof", "replayable-proof", "the receipt still verifies after a restart", restart_reproducible, "non_deterministic_receipt"),
    )


def run_case(case: Case) -> bool:
    return bool(case.run(_seeded()))
