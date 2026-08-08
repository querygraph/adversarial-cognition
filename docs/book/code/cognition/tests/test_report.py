"""Tests for hard gates, report assembly, and the public-corpus inventory."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from adversarial_cognition.adapters import CaseOutcome, SystemReport, execute_marciana
from adversarial_cognition.cases import cases
from adversarial_cognition.corpora import PUBLIC_CORPORA, inventory, load_dmr
from adversarial_cognition.report import (
    CATEGORY_GATES,
    GATE_NAMES,
    assert_bounded,
    build_report,
    corpus_digest,
    corpus_manifest,
    hard_gates,
    overall_status,
    quality,
    receipt_mismatches,
)

SEED_PLAINTEXT = (
    "USD per kg",
    "volcanic soil",
    "ignore all previous instructions",
)


def reference_outcomes() -> tuple[CaseOutcome, ...]:
    return execute_marciana(cases(), 1).outcomes


def reference_report() -> dict[str, object]:
    systems = (execute_marciana(cases(), 1),)
    metadata = {"model": "reference-smoke-v1", "provider": "local"}
    manifest = corpus_manifest(cases())
    return build_report(
        metadata, corpus_digest(manifest), systems, 0, 10.0, 1.0, inventory({})
    )


class HardGateTests(unittest.TestCase):
    def test_reference_run_holds_every_gate_at_zero(self) -> None:
        gates = hard_gates(reference_outcomes(), 0)
        self.assertEqual(set(gates), set(GATE_NAMES))
        self.assertEqual(sum(gates.values()), 0)

    def test_failed_safety_case_trips_its_gate(self) -> None:
        outcomes = reference_outcomes()
        broken = tuple(
            replace(outcome, correct=False) if outcome.case_id == "forged-source" else outcome
            for outcome in outcomes
        )
        self.assertEqual(hard_gates(broken, 0)["invalid_provenance_accepted"], 1)

    def test_tenant_leak_counts_as_cross_scope_not_generic(self) -> None:
        outcomes = tuple(
            replace(outcome, correct=False) if outcome.case_id == "isolation-tenant" else outcome
            for outcome in reference_outcomes()
        )
        gates = hard_gates(outcomes, 0)
        self.assertEqual(gates["cross_scope_leakage"], 1)
        self.assertEqual(gates["unauthorized_disclosure"], 0)

    def test_every_safety_category_maps_to_a_gate(self) -> None:
        for case in cases():
            if case.category in CATEGORY_GATES:
                self.assertIn(CATEGORY_GATES[case.category], GATE_NAMES)

    def test_receipt_mismatch_detection(self) -> None:
        outcomes = reference_outcomes()
        self.assertEqual(receipt_mismatches(outcomes, outcomes), 0)
        drifted = (replace(outcomes[0], receipt="sha256:" + "f" * 64),) + outcomes[1:]
        self.assertEqual(receipt_mismatches(outcomes, drifted), 1)


class ReportTests(unittest.TestCase):
    def test_report_status_and_required_sections(self) -> None:
        report = reference_report()
        self.assertEqual(report["status"], "pass")
        for key in ("benchmark", "metadata", "hard_gates", "systems", "cases", "quality", "performance", "public_corpora"):
            self.assertIn(key, report)
        self.assertEqual(report["quality"]["accuracy"], 1.0)
        self.assertEqual(report["quality"]["unsupported_cases"], 0)

    def test_unsupported_cases_never_count_toward_accuracy(self) -> None:
        outcomes = reference_outcomes()
        declared = (replace(outcomes[0], correct=False, supported=False),) + outcomes[1:]
        measured = quality(declared)
        self.assertEqual(measured["accuracy"], 1.0)
        self.assertEqual(measured["unsupported_cases"], 1)

    def test_report_contains_no_memory_plaintext(self) -> None:
        rendered = json.dumps(reference_report())
        for phrase in SEED_PLAINTEXT:
            self.assertNotIn(phrase, rendered)

    def test_unbounded_strings_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            assert_bounded({"note": "x" * 1_000})
        with self.assertRaises(ValueError):
            assert_bounded({"rows": [{"note": "line\nbreak"}]})

    def test_status_fails_on_any_gate_and_incompletes_without_marciana(self) -> None:
        executed = (SystemReport("marciana", "v1", "executed"),)
        self.assertEqual(overall_status({"gate": 0}, executed), "pass")
        self.assertEqual(overall_status({"gate": 1}, executed), "fail")
        errored = (SystemReport("marciana", "v1", "error"),)
        self.assertEqual(overall_status({"gate": 0}, errored), "incomplete")

    def test_corpus_digest_pins_expectations(self) -> None:
        manifest = corpus_manifest(cases())
        self.assertEqual(corpus_digest(manifest), corpus_digest(manifest))
        manifest_copy = json.loads(json.dumps(manifest))
        manifest_copy["cases"][0]["expected_allowed"] = False
        self.assertNotEqual(corpus_digest(manifest), corpus_digest(manifest_copy))

    def test_manifest_fixture_matches_code_defined_corpus(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "marciana-adversarial-v1" / "manifest.json"
        pinned = json.loads(fixture.read_text(encoding="utf-8"))
        manifest = corpus_manifest(cases())
        self.assertEqual(pinned, {"digest": corpus_digest(manifest), "manifest": manifest})


class PublicCorpusTests(unittest.TestCase):
    def test_unconfigured_corpora_are_inventoried_not_skipped(self) -> None:
        report = inventory({})
        self.assertEqual(len(report), len(PUBLIC_CORPORA))
        for name, entry in report.items():
            with self.subTest(name):
                self.assertEqual(entry["status"], "unavailable")
                self.assertTrue(entry["missing_configuration"])
                self.assertTrue(entry["revision"])

    def test_dmr_normalized_jsonl_loads_through_strict_contract(self) -> None:
        row = {
            "case_id": "dmr:0",
            "query": "what did the speaker say",
            "as_of": "2026-01-01",
            "expected_ids": ["session-1"],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as handle:
            handle.write(json.dumps(row) + "\n")
            path = Path(handle.name)
        try:
            loaded = load_dmr(path)
        finally:
            path.unlink()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].case_id, "dmr:0")

    def test_configured_corpus_failure_reports_error(self) -> None:
        report = inventory({"MARCIANA_ADVERSARIAL_DMR_PATH": "/nonexistent/dmr.jsonl"})
        self.assertEqual(report["dmr"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
