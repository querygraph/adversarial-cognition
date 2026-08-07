"""Tests for comparative Markdown rendering."""

from __future__ import annotations

import unittest

from render_results import render


class ComparativeRenderingTests(unittest.TestCase):
    def test_supported_case_results_are_not_presented_as_an_ordinal_ranking(self) -> None:
        report = {
            "benchmark": "test",
            "corpus_digest": "sha256:test",
            "status": "pass",
            "metadata": {"profile": "test", "provider": "local"},
            "hard_gates": {},
            "systems": {
                "marciana": {
                    "status": "executed",
                    "adapter_version": "reference",
                    "cases": [
                        {
                            "case_id": "one",
                            "category": "retrieval",
                            "correct": True,
                            "supported": True,
                        }
                    ],
                }
            },
        }

        output = render(report)

        self.assertIn("not an ordinal ranking", output)
        self.assertIn("Correct / supported", output)
        self.assertIn("1/1 (100%)", output)


if __name__ == "__main__":
    unittest.main()
