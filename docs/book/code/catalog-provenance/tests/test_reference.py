"""Tests for the reference catalog's provable-transaction semantics."""

from __future__ import annotations

import unittest
from dataclasses import replace

from catalog_provenance.backend import ReferenceCatalog, policy_digest

POLICY = "read allowed for analytics"


def seeded() -> ReferenceCatalog:
    cat = ReferenceCatalog()
    cat.create("t", "did:key:op")
    return cat


class ConcurrencyTests(unittest.TestCase):
    def test_compare_and_swap_rejects_stale(self) -> None:
        cat = seeded()
        head = cat.pointer("t")
        self.assertTrue(cat.commit("t", head, "a", "did:key:op", POLICY, "n1", "k1").ok)
        stale = cat.commit("t", head, "b", "did:key:op", POLICY, "n2", "k2")
        self.assertFalse(stale.ok)
        self.assertEqual(stale.error, "stale-metadata")

    def test_rejected_commit_leaves_no_evidence(self) -> None:
        cat = seeded()
        head = cat.pointer("t")
        cat.commit("t", head, "a", "did:key:op", POLICY, "n1", "k1")
        before = (len(cat.audit), len(cat.outbox), len(cat.lineage))
        cat.commit("t", head, "b", "did:key:op", POLICY, "n2", "k2")  # stale
        self.assertEqual((len(cat.audit), len(cat.outbox), len(cat.lineage)), before)


class IdempotencyTests(unittest.TestCase):
    def test_retry_returns_identical_receipt_no_double_apply(self) -> None:
        cat = seeded()
        head = cat.pointer("t")
        first = cat.commit("t", head, "u", "did:key:op", POLICY, "n1", "k")
        pointer = cat.pointer("t")
        second = cat.commit("t", head, "u", "did:key:op", POLICY, "n2", "k")
        self.assertEqual(first.receipt, second.receipt)
        self.assertEqual(cat.pointer("t"), pointer)

    def test_idempotency_durable_across_restart(self) -> None:
        cat = seeded()
        head = cat.pointer("t")
        first = cat.commit("t", head, "u", "did:key:op", POLICY, "n1", "k")
        second = cat.restart().commit("t", head, "u", "did:key:op", POLICY, "n2", "k")
        self.assertEqual(first.receipt, second.receipt)


class ProofTests(unittest.TestCase):
    def test_receipt_verifies_and_forgery_fails(self) -> None:
        cat = seeded()
        out = cat.commit("t", cat.pointer("t"), "u", "did:key:op", POLICY, "n1", "k")
        self.assertTrue(cat.replay(out.receipt))
        forged = replace(out.receipt, response_hash="sha256:" + "0" * 64)
        self.assertFalse(forged.verifies())
        self.assertFalse(cat.replay(forged))

    def test_receipts_chain(self) -> None:
        cat = seeded()
        a = cat.commit("t", cat.pointer("t"), "u1", "did:key:op", POLICY, "n1", "k1")
        b = cat.commit("t", cat.pointer("t"), "u2", "did:key:op", POLICY, "n2", "k2")
        self.assertEqual(b.receipt.prev_receipt, a.receipt.receipt_hash)


class GovernedScanTests(unittest.TestCase):
    def test_scan_receipt_binds_policy(self) -> None:
        cat = seeded()
        out = cat.scan("t", "did:key:op", POLICY)
        self.assertTrue(out.scan_receipt.verifies((policy_digest(POLICY),)))
        self.assertFalse(out.scan_receipt.verifies((policy_digest("other"),)))


class RedactionTests(unittest.TestCase):
    def test_evidence_is_hash_only(self) -> None:
        cat = seeded()
        secret = "s3://warehouse/AKIASECRET/loc"
        cat.commit("t", cat.pointer("t"), secret, "did:key:op", POLICY, "n1", "k")
        for blob in cat.audit + cat.outbox + cat.lineage:
            self.assertNotIn("AKIA", blob)
            self.assertTrue(blob.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
