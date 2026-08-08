"""The reference guard must pass every case, and gates must never trip on it."""

from __future__ import annotations

import unittest

from capability_adversarial.adapters import run_reference
from capability_adversarial.cases import CAPABILITIES, GATES, cases, run_case


class ReferenceTest(unittest.TestCase):
    def test_every_case_passes(self) -> None:
        for case in cases():
            with self.subTest(case=case.case_id):
                self.assertTrue(run_case(case), f"{case.case_id} failed")

    def test_reference_report_is_clean(self) -> None:
        report = run_reference(cases())
        self.assertEqual(report["summary"]["supported"], len(cases()))
        self.assertEqual(report["summary"]["correct"], len(cases()))
        self.assertEqual(sum(report["hard_gates"].values()), 0)
        self.assertEqual(sorted(report["capabilities"]), sorted(CAPABILITIES))

    def test_every_gate_is_guarded_by_a_case(self) -> None:
        guarded = {c.gate for c in cases() if c.gate}
        self.assertEqual(guarded, set(GATES))

    def test_every_case_capability_is_declared(self) -> None:
        for case in cases():
            self.assertIn(case.capability, CAPABILITIES)


if __name__ == "__main__":
    unittest.main()
