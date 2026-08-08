"""Test the shared adapter driver against a reference-backed CatalogSystem."""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import protocol
from protocol import CatalogSystem, Unsupported

from catalog_provenance.backend import ReferenceCatalog, policy_digest
from catalog_provenance.cases import CAPABILITIES, cases


class ReferenceSystem(CatalogSystem):
    """Wrap the in-process reference catalog behind the adapter interface."""

    name = "reference-wrap"
    version = "1"
    capabilities = frozenset(CAPABILITIES)

    def reset(self) -> None:
        self.cat = ReferenceCatalog()
        self.cat.create("sales.events", "did:key:op")
        self._nonce = 0

    def _n(self) -> str:
        self._nonce += 1
        return f"n{self._nonce}"

    def create(self, table: str) -> None:
        self.cat.create(table, "did:key:op")

    def pointer(self, table: str) -> str:
        return self.cat.pointer(table)

    def commit(self, table, expected, update, idempotency_key="") -> dict:
        out = self.cat.commit(table, expected, update, "did:key:op",
                              protocol.POLICY if update != protocol.SECRET else protocol.POLICY,
                              self._n(), idempotency_key)
        r = out.receipt
        return {"ok": out.ok,
                "receipt": {"receipt_hash": r.receipt_hash, "prev_receipt": r.prev_receipt,
                            "response_hash": r.response_hash, "_obj": r} if r else None}

    def audit_count(self) -> int:
        return len(self.cat.audit)

    def outbox_count(self) -> int:
        return len(self.cat.outbox)

    def lineage_count(self) -> int:
        return len(self.cat.lineage)

    def replay(self, receipt: dict) -> bool:
        obj = receipt.get("_obj")
        if obj is None or receipt["response_hash"] != obj.response_hash:
            # forged copy: reconstruct with the tampered hash
            from dataclasses import replace
            obj = replace(obj, response_hash=receipt["response_hash"]) if obj else None
        return bool(obj) and self.cat.replay(obj)

    def scan(self, table, policy) -> dict:
        out = self.cat.scan(table, "did:key:op", policy)
        sr = out.scan_receipt
        return {"ok": out.ok, "scan_receipt": {"_obj": sr}}

    def scan_verifies(self, scan_receipt, policy) -> bool:
        return scan_receipt["_obj"].verifies((policy_digest(policy),))

    def tombstone(self, table) -> dict:
        out = self.cat.tombstone(table, "did:key:op", protocol.POLICY, self._n())
        return {"ok": out.ok, "receipt": {"op": out.receipt.op} if out.receipt else {}}

    def evidence_blobs(self) -> list[str]:
        return self.cat.audit + self.cat.outbox + self.cat.lineage

    def restart(self) -> None:
        self.cat = self.cat.restart()


def drive(system: CatalogSystem, capability_override=None) -> dict:
    suite = cases()
    request = {"cases": [
        {"case_id": c.case_id, "capability": c.capability, "category": c.category,
         "gate": c.gate, "description": c.description}
        for c in suite
    ]}
    sys.stdin = io.StringIO(json.dumps(request))
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            protocol.run(system)
    finally:
        sys.stdin = sys.__stdin__
    return json.loads(buf.getvalue())


class DriverTests(unittest.TestCase):
    def test_reference_backed_system_passes_all(self) -> None:
        out = drive(ReferenceSystem())
        supported = [c for c in out["cases"] if c["supported"]]
        self.assertEqual(len(supported), len(cases()))
        self.assertTrue(all(c["correct"] for c in supported), out["cases"])

    def test_commit_only_system_declares_rest_unsupported(self) -> None:
        class CommitOnly(ReferenceSystem):
            capabilities = frozenset({"commit", "compare-and-swap"})

        out = drive(CommitOnly())
        by = {c["case_id"]: c for c in out["cases"]}
        self.assertTrue(by["commit-fresh"]["supported"] and by["commit-fresh"]["correct"])
        self.assertTrue(by["cas-stale-rejected"]["supported"])
        self.assertFalse(by["governed-scan-receipt"]["supported"])
        self.assertFalse(by["replay-verifies"]["supported"])


if __name__ == "__main__":
    unittest.main()
