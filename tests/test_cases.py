"""Tests for the adversarial scenario corpus and its evaluation rules."""

from __future__ import annotations

import unittest

from adversarial_cognition.backend import Decision
from adversarial_cognition.cases import Case, cases, run_case


class CorpusTests(unittest.TestCase):
    def test_every_case_passes_on_the_reference_backend(self) -> None:
        for case in cases():
            with self.subTest(case.case_id):
                correct, decision = run_case(case)
                self.assertTrue(correct, f"{case.case_id}: {decision}")

    def test_case_ids_are_unique_and_bounded(self) -> None:
        suite = cases()
        ids = [case.case_id for case in suite]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(0 < len(case_id) <= 64 for case_id in ids))

    def test_corpus_covers_every_goal_area(self) -> None:
        categories = {case.category for case in cases()}
        self.assertLessEqual(
            {
                "retrieval",
                "temporal",
                "abstention",
                "authorization",
                "provenance",
                "mutation",
                "replay",
                "recovery",
                "forget",
                "reproducibility",
                "robustness",
            },
            categories,
        )


class EvaluationRuleTests(unittest.TestCase):
    def evaluated(self, case: Case) -> bool:
        correct, _ = run_case(case)
        return correct

    def test_wrong_allowed_expectation_fails(self) -> None:
        case = Case("x", "retrieval", "flipped", lambda backend: Decision(True), False)
        self.assertFalse(self.evaluated(case))

    def test_forbidden_id_fails_even_when_allowed(self) -> None:
        run = lambda backend: Decision(True, ("private-farm",))
        case = Case("x", "robustness", "leak", run, True, forbidden_ids=("private-farm",))
        self.assertFalse(self.evaluated(case))

    def test_must_abstain_rejects_any_ids(self) -> None:
        run = lambda backend: Decision(True, ("soil",))
        case = Case("x", "abstention", "answered", run, True, must_abstain=True)
        self.assertFalse(self.evaluated(case))

    def test_expected_ids_compare_as_ranked_prefix(self) -> None:
        run = lambda backend: Decision(True, ("first", "second", "extra"))
        case = Case("x", "retrieval", "prefix", run, True, ("first", "second"))
        self.assertTrue(self.evaluated(case))
        reordered = Case("x", "retrieval", "prefix", run, True, ("second",))
        self.assertFalse(self.evaluated(reordered))


if __name__ == "__main__":
    unittest.main()
