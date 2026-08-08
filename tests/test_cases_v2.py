"""Tests for the v2 corpus: authenticated re-expression of the v1 intents."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adversarial_cognition.cases import cases
from adversarial_cognition.cases_v2 import cases_v2, run_case_v2
from adversarial_cognition.report import corpus_digest, corpus_manifest_v2

PINNED = ROOT / "fixtures" / "marciana-adversarial-v2" / "manifest.json"


class CorpusV2Test(unittest.TestCase):
    def test_every_case_passes_on_authenticated_reference(self) -> None:
        for case in cases_v2():
            correct, decision = run_case_v2(case)
            self.assertTrue(correct, f"{case.case_id}: {decision}")

    def test_same_eighteen_intents_as_v1(self) -> None:
        # Q2 decision: identical case ids, categories, and expectations, so
        # v1→v2 deltas are attributable to the method changes alone.
        v1 = {(c.case_id, c.category, c.expected_allowed, c.expected_ids,
               c.must_abstain, c.forbidden_ids) for c in cases()}
        v2 = {(c.case_id, c.category, c.expected_allowed, c.expected_ids,
               c.must_abstain, c.forbidden_ids) for c in cases_v2()}
        self.assertEqual(v1, v2)

    def test_ids_bounded_and_unique(self) -> None:
        suite = cases_v2()
        ids = [case.case_id for case in suite]
        self.assertEqual(len(ids), len(set(ids)))
        for case in suite:
            _, decision = run_case_v2(case)
            self.assertLessEqual(len(decision.ids), 8)
            for memory_id in decision.ids:
                self.assertLessEqual(len(memory_id), 64)


class CorpusV2DigestFrozenTest(unittest.TestCase):
    def test_v2_digest_matches_pinned_fixture(self) -> None:
        pinned = json.loads(PINNED.read_text(encoding="utf-8"))
        manifest = corpus_manifest_v2(cases_v2())
        self.assertEqual(corpus_digest(manifest), pinned["digest"])
        self.assertEqual(manifest, pinned["manifest"])

    def test_manifest_pins_identity_model_and_tracks(self) -> None:
        # The digest must cover the semantics that changed in v2, not only
        # the case list (finding 9).
        pinned = json.loads(PINNED.read_text(encoding="utf-8"))
        manifest = pinned["manifest"]
        self.assertIn("identity_model", manifest)
        self.assertIn("tracks", manifest)
        self.assertIn("oversized-query",
                      str(manifest["tracks"]["agent-memory"]))

    def test_v2_digest_differs_from_v1(self) -> None:
        v1 = json.loads(
            (ROOT / "fixtures" / "marciana-adversarial-v1" / "manifest.json")
            .read_text(encoding="utf-8")
        )
        v2 = json.loads(PINNED.read_text(encoding="utf-8"))
        self.assertNotEqual(v1["digest"], v2["digest"])


if __name__ == "__main__":
    unittest.main()
