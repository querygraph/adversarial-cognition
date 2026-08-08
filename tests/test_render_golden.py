"""Golden tests freezing the published v1 rendering and corpus digest.

MARCIANA-ADVERSARIAL-v2 changes the renderer and report builder. These tests
pin the v1 surface byte-for-byte first, so any v2 work that drifts the
published v1 document or its pinned digest fails immediately.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adversarial_cognition.cases import cases
from adversarial_cognition.report import corpus_digest, corpus_manifest
from render_results import render

GOLDEN_REPORT = ROOT / "fixtures" / "golden" / "marciana-adversarial-v1-comparative.json"
PUBLISHED_RESULTS = ROOT / "docs" / "RESULTS.md"
PINNED_MANIFEST = ROOT / "fixtures" / "marciana-adversarial-v1" / "manifest.json"


class V1RenderGoldenTest(unittest.TestCase):
    def test_published_results_render_byte_for_byte(self) -> None:
        report = json.loads(GOLDEN_REPORT.read_text(encoding="utf-8"))
        self.assertEqual(
            render(report),
            PUBLISHED_RESULTS.read_text(encoding="utf-8"),
            "v1 rendering drifted from the published docs/RESULTS.md",
        )


class V1CorpusDigestFrozenTest(unittest.TestCase):
    def test_v1_corpus_digest_matches_pinned_fixture(self) -> None:
        pinned = json.loads(PINNED_MANIFEST.read_text(encoding="utf-8"))
        recomputed = corpus_digest(corpus_manifest(cases()))
        self.assertEqual(recomputed, pinned["digest"], "v1 corpus digest drifted")
        self.assertEqual(
            pinned["digest"],
            "sha256:d879b8a53039d84134bf8b35f21a398c497b94605bddf1a4995854aa1cb798b9",
            "pinned v1 digest changed — v1 must never be re-cut",
        )


if __name__ == "__main__":
    unittest.main()
