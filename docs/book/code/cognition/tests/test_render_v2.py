"""Tests for v2 track-grouped rendering and report building.

The v2 rule — systems are compared only within a track — is enforced
structurally by the renderer, not by a caption. These tests exercise the
version-switched report builder, the per-track rendering, and the
cross-track-table detector itself.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adversarial_cognition.adapters import (
    CaseOutcome,
    SystemReport,
    _parse_external_outcomes,
)
from adversarial_cognition.cases import cases
from adversarial_cognition.report import BENCHMARK, BENCHMARK_V2, build_report
from render_results import assert_no_cross_track_table, render, render_v2

import json

SUITE = cases()


def outcome(case, correct=True, supported=True):
    return CaseOutcome(
        case.case_id, case.category, correct and supported,
        case.expected_allowed if supported else False,
        case.expected_ids if (correct and supported) else (),
        "sha256:receipt" if supported else "", 10.0, supported,
    )


def system(name, interface="direct-api", harness=None, correct=True):
    return SystemReport(
        name, f"{name}-adapter", "executed",
        interface=interface,
        outcomes=tuple(outcome(case, correct) for case in SUITE),
        harness=harness,
    )


HARNESS = {
    "model": "llama3.1:latest", "seed": 7, "temperature": 0,
    "num_ctx": 8192, "max_turns": 6,
    "prompt_digest": "sha256:promptdigest", "tool_contract": "marciana-agent-tools-v1",
}


def v2_report(systems):
    return build_report(
        {"profile": "test", "provider": "test"},
        "sha256:corpus", systems, 0, 1.0, 1.0, {}, benchmark=BENCHMARK_V2,
    )


class BuildReportV2Test(unittest.TestCase):
    def test_v2_stamps_track_and_groups(self) -> None:
        report = v2_report((
            system("marciana"),
            system("letta-agent", interface="agent-loop", harness=HARNESS),
        ))
        self.assertEqual(report["systems"]["marciana"]["track"], "memory-store")
        self.assertEqual(report["systems"]["letta-agent"]["track"], "agent-memory")
        self.assertEqual(report["tracks"]["memory-store"], ["marciana"])
        self.assertEqual(report["tracks"]["agent-memory"], ["letta-agent"])

    def test_v1_report_has_no_track_keys(self) -> None:
        report = build_report(
            {"profile": "test", "provider": "test"},
            "sha256:corpus", (system("marciana"),), 0, 1.0, 1.0, {},
            benchmark=BENCHMARK,
        )
        self.assertNotIn("tracks", report)
        self.assertNotIn("track", report["systems"]["marciana"])


class RenderV2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.report = v2_report((
            system("marciana"),
            system("mem0", correct=False),
            system("marciana-agent", interface="agent-loop", harness=HARNESS),
            system("memfs-agent", interface="agent-loop", harness=HARNESS),
            SystemReport("letta", "adapter", "unavailable",
                         missing_configuration=("LETTA_CMD",)),
        ))
        self.rendered = render(self.report)

    def test_one_section_per_track(self) -> None:
        self.assertIn("## Memory-store track", self.rendered)
        self.assertIn("## Agent-memory track", self.rendered)

    def test_harness_line_rendered_for_agent_track(self) -> None:
        self.assertIn("**Shared harness:** model `llama3.1:latest`", self.rendered)

    def test_unavailable_rows_are_trackless(self) -> None:
        self.assertIn("## Not executed", self.rendered)
        self.assertIn("| letta | unavailable | LETTA_CMD |", self.rendered)

    def test_no_table_mixes_tracks(self) -> None:
        # The renderer itself enforces this before returning, but assert the
        # detector agrees on the final document too.
        assert_no_cross_track_table(self.rendered, self.report)

    def test_dual_product_lands_one_row_per_track(self) -> None:
        # A product shipping both layers appears once per track under
        # distinct names; each name must appear in exactly one track section.
        memory_section = self.rendered.split("## Agent-memory track")[0]
        agent_section = self.rendered.split("## Agent-memory track")[1]
        self.assertIn("| marciana |", memory_section)
        self.assertNotIn("| marciana |", agent_section)
        self.assertIn("| marciana-agent |", agent_section)

    def test_detector_rejects_mixed_table(self) -> None:
        mixed = "\n".join((
            "| System | Score |",
            "|--------|-------|",
            "| marciana | 18 |",
            "| marciana-agent | 12 |",
        ))
        with self.assertRaises(ValueError):
            assert_no_cross_track_table(mixed, self.report)

    def test_unknown_version_rejected(self) -> None:
        bad = dict(self.report, benchmark="MARCIANA-ADVERSARIAL-v9")
        with self.assertRaises(ValueError):
            render(bad)


class ParseV2ValidationTest(unittest.TestCase):
    def payload(self, **overrides) -> str:
        body = {
            "adapter_version": "fake-1",
            "interface": "agent-loop",
            "harness": dict(HARNESS),
            "cases": [
                {"case_id": case.case_id, "correct": True,
                 "allowed": case.expected_allowed,
                 "returned_ids": list(case.expected_ids), "supported": True}
                for case in SUITE
            ],
        }
        body.update(overrides)
        for key in [k for k, v in body.items() if v is None]:
            del body[key]
        return json.dumps(body)

    def test_v2_requires_interface(self) -> None:
        with self.assertRaises(ValueError):
            _parse_external_outcomes(
                self.payload(interface=None), SUITE, benchmark_version=2
            )

    def test_v2_agent_loop_requires_harness(self) -> None:
        with self.assertRaises(ValueError):
            _parse_external_outcomes(
                self.payload(harness=None), SUITE, benchmark_version=2
            )

    def test_v2_harness_missing_keys_rejected(self) -> None:
        broken = dict(HARNESS)
        del broken["prompt_digest"]
        with self.assertRaises(ValueError):
            _parse_external_outcomes(
                self.payload(harness=broken), SUITE, benchmark_version=2
            )

    def test_v2_valid_agent_loop_parses_harness(self) -> None:
        version, interface, harness, outcomes = _parse_external_outcomes(
            self.payload(), SUITE, benchmark_version=2
        )
        self.assertEqual(interface, "agent-loop")
        self.assertEqual(harness["model"], "llama3.1:latest")
        self.assertEqual(len(outcomes), len(SUITE))

    def test_v1_defaults_unchanged(self) -> None:
        version, interface, harness, outcomes = _parse_external_outcomes(
            self.payload(interface=None, harness=None), SUITE
        )
        self.assertEqual(interface, "direct-api")
        self.assertIsNone(harness)


if __name__ == "__main__":
    unittest.main()
