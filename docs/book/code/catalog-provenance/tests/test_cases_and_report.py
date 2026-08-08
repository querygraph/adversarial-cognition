"""Tests for the case corpus, gates, report assembly, and adapter protocol."""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from catalog_provenance.adapters import execute_catalogs, run_reference
from catalog_provenance.cases import CAPABILITIES, GATES, cases, run_case
from catalog_provenance.report import (
    assert_bounded,
    build_report,
    corpus_digest,
    corpus_manifest,
    hard_gates,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "catalog-provenance-v1" / "manifest.json"


class CorpusTests(unittest.TestCase):
    def test_reference_passes_every_case(self) -> None:
        for case in cases():
            with self.subTest(case.case_id):
                self.assertTrue(run_case(case))

    def test_case_ids_unique_and_gates_valid(self) -> None:
        suite = cases()
        ids = [c.case_id for c in suite]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue({c.gate for c in suite if c.gate} <= set(GATES))
        self.assertTrue({c.capability for c in suite} <= set(CAPABILITIES))

    def test_manifest_fixture_matches_code(self) -> None:
        manifest = corpus_manifest(cases())
        pinned = json.loads(FIXTURE.read_text())
        self.assertEqual(pinned, {"digest": corpus_digest(manifest), "manifest": manifest})


class GateTests(unittest.TestCase):
    def test_reference_holds_all_gates_zero(self) -> None:
        ref = run_reference(cases())
        self.assertEqual(sum(ref["hard_gates"].values()), 0)
        self.assertEqual(ref["summary"]["correct"], ref["summary"]["supported"])

    def test_failed_supported_case_trips_its_gate(self) -> None:
        rows = [{"case_id": "x", "gate": "lost_update_accepted", "supported": True, "correct": False}]
        self.assertEqual(hard_gates(rows)["lost_update_accepted"], 1)

    def test_unsupported_case_never_trips_a_gate(self) -> None:
        rows = [{"case_id": "x", "gate": "lost_update_accepted", "supported": False, "correct": False}]
        self.assertEqual(sum(hard_gates(rows).values()), 0)


class ReportTests(unittest.TestCase):
    def test_report_status_and_bounded(self) -> None:
        report = build_report({"harness": "test"}, "sha256:abc",
                              [run_reference(cases())])
        self.assertEqual(report["status"], "pass")
        json.dumps(report)  # serializable

    def test_unbounded_string_rejected(self) -> None:
        with self.assertRaises(ValueError):
            assert_bounded({"note": "x" * 500})


class AdapterProtocolTests(unittest.TestCase):
    def test_unconfigured_catalogs_unavailable(self) -> None:
        results = execute_catalogs(("reference", "lakecat", "polaris"), cases(), {})
        by = {r["catalog"]: r for r in results}
        self.assertEqual(by["reference"]["status"], "executed")
        self.assertEqual(by["lakecat"]["status"], "unavailable")
        self.assertEqual(by["polaris"]["status"], "unavailable")

    def test_stub_adapter_capability_gated(self) -> None:
        # An adapter claiming only {commit} may support only commit cases even
        # if it marks others supported=true.
        stub = (
            "import json,sys;"
            "r=json.load(sys.stdin);"
            "print(json.dumps({'adapter_version':'stub-1','capabilities':['commit'],"
            "'cases':[{'case_id':c['case_id'],'supported':True,'correct':True} for c in r['cases']]}))"
        )
        environ = {"CATALOG_PROVENANCE_NESSIE_CMD": f"{sys.executable} -c \"{stub}\""}
        results = execute_catalogs(("nessie",), cases(), environ)
        nessie = results[0]
        self.assertEqual(nessie["status"], "executed")
        supported = [c for c in nessie["cases"] if c["supported"]]
        self.assertTrue(all(c["capability"] == "commit" for c in supported))
        self.assertGreater(nessie["summary"]["unsupported"], 0)

    def test_unknown_catalog_rejected(self) -> None:
        with self.assertRaises(ValueError):
            execute_catalogs(("reference", "surprise"), cases(), {})


if __name__ == "__main__":
    unittest.main()
