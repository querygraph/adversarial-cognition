"""The adapter driver: capability-declared scoring and gate accounting."""

from __future__ import annotations

import json
import unittest

from capability_adversarial.adapters import _parse, execute_external
from capability_adversarial.cases import cases
from capability_adversarial.report import hard_gates


def _payload(claim: dict[str, bool], capabilities: list[str]) -> str:
    rows = [{"case_id": c.case_id, "supported": True, "correct": claim.get(c.case_id, True)}
            for c in cases()]
    return json.dumps({"adapter_version": "fake-1", "capabilities": capabilities, "cases": rows})


class DriverTest(unittest.TestCase):
    def test_unclaimed_capability_is_unsupported_not_failed(self) -> None:
        # An adapter that reports a case correct but does NOT claim its
        # capability must be scored unsupported, never as a pass — no faking.
        suite = cases()
        _, caps, rows = _parse(_payload({}, capabilities=[]), suite)
        self.assertTrue(all(not r["supported"] for r in rows))
        self.assertEqual(sum(hard_gates(rows).values()), 0)  # unsupported never trips a gate

    def test_claimed_but_wrong_trips_the_gate(self) -> None:
        # A system that claims revocation but honors a revoked capability trips
        # the revoked_capability_honored gate — but only for the claimed cases.
        suite = cases()
        _, caps, rows = _parse(
            _payload({"revoke-by-id": False}, capabilities=["revocation"]), suite)
        gates = hard_gates(rows)
        self.assertEqual(gates["revoked_capability_honored"], 1)
        # A case whose capability was not claimed stays unsupported, no gate.
        forged = next(r for r in rows if r["case_id"] == "forged-capability-rejected")
        self.assertFalse(forged["supported"])
        self.assertEqual(gates["forged_capability_accepted"], 0)

    def test_adapter_must_report_every_case(self) -> None:
        bad = json.dumps({"capabilities": [], "cases": [{"case_id": "mint-authorized",
                                                          "supported": True, "correct": True}]})
        with self.assertRaises(ValueError):
            _parse(bad, cases())

    def test_unavailable_when_unconfigured(self) -> None:
        result = execute_external("ucan", "MISSING_CMD", cases(), {})
        self.assertEqual(result["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
