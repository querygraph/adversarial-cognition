"""Tests for the comparative-system adapter protocol."""

from __future__ import annotations

import json
import ast
import sys
import tempfile
import unittest
from pathlib import Path

from adversarial_cognition.adapters import (
    EXTERNAL_SYSTEMS,
    _parse_external_outcomes,
    execute_external,
    execute_marciana,
    execute_systems,
)
from adversarial_cognition.cases import cases

STUB_ADAPTER = """
import json, sys
request = json.load(sys.stdin)
print(json.dumps({
    "adapter_version": "stub-adapter-1",
    "cases": [
        {
            "case_id": case["case_id"],
            "correct": True,
            "allowed": case["expected_allowed"],
            "returned_ids": case["expected_ids"],
            "receipt": "sha256:" + "0" * 64,
            "latency_us": 1.0,
            "supported": index > 0,
        }
        for index, case in enumerate(request["cases"])
    ]
}))
"""


class MarcianaAdapterTests(unittest.TestCase):
    def test_executes_every_case_correctly(self) -> None:
        suite = cases()
        report = execute_marciana(suite, 1)
        self.assertEqual(report.status, "executed")
        self.assertEqual(len(report.outcomes), len(suite))
        self.assertTrue(all(outcome.correct for outcome in report.outcomes))


class ExternalAdapterTests(unittest.TestCase):
    def test_unconfigured_system_is_unavailable_with_named_variable(self) -> None:
        report = execute_external("mem0", "MARCIANA_ADVERSARIAL_MEM0_CMD", cases(), 1, {})
        self.assertEqual(report.status, "unavailable")
        self.assertEqual(report.missing_configuration, ("MARCIANA_ADVERSARIAL_MEM0_CMD",))

    def test_configured_stub_command_executes(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
            handle.write(STUB_ADAPTER)
            stub = handle.name
        try:
            environ = {"MARCIANA_ADVERSARIAL_MEM0_CMD": f"{sys.executable} {stub}"}
            report = execute_external(
                "mem0", "MARCIANA_ADVERSARIAL_MEM0_CMD", cases(), 1, environ
            )
        finally:
            Path(stub).unlink()
        self.assertEqual(report.status, "executed")
        self.assertEqual(report.adapter_version, "stub-adapter-1")
        self.assertTrue(all(outcome.correct for outcome in report.outcomes))
        self.assertEqual(sum(not o.supported for o in report.outcomes), 1)
        self.assertEqual(report.as_dict()["unsupported_cases"], 1)

    def test_interface_defaults_to_direct_api(self) -> None:
        # The stub emits no `interface`; it must default to direct-api.
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
            handle.write(STUB_ADAPTER)
            stub = handle.name
        try:
            environ = {"MARCIANA_ADVERSARIAL_MEM0_CMD": f"{sys.executable} {stub}"}
            report = execute_external("mem0", "MARCIANA_ADVERSARIAL_MEM0_CMD", cases(), 1, environ)
        finally:
            Path(stub).unlink()
        self.assertEqual(report.interface, "direct-api")
        self.assertEqual(report.as_dict()["interface"], "direct-api")

    def test_interface_is_surfaced_from_adapter(self) -> None:
        # An adapter declaring agent-loop is recorded as such — metadata only.
        stub_src = STUB_ADAPTER.replace(
            '"adapter_version": "stub-adapter-1",',
            '"adapter_version": "stub-adapter-1", "interface": "agent-loop",',
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
            handle.write(stub_src)
            stub = handle.name
        try:
            environ = {"MARCIANA_ADVERSARIAL_LETTA_CMD": f"{sys.executable} {stub}"}
            report = execute_external("letta", "MARCIANA_ADVERSARIAL_LETTA_CMD", cases(), 1, environ)
        finally:
            Path(stub).unlink()
        self.assertEqual(report.as_dict()["interface"], "agent-loop")

    def test_marciana_declares_direct_api(self) -> None:
        self.assertEqual(execute_marciana(cases(), 1).as_dict()["interface"], "direct-api")

    def test_malformed_adapter_output_reports_error(self) -> None:
        environ = {"MARCIANA_ADVERSARIAL_MEM0_CMD": f'{sys.executable} -c "print(42)"'}
        report = execute_external("mem0", "MARCIANA_ADVERSARIAL_MEM0_CMD", cases(), 1, environ)
        self.assertEqual(report.status, "error")
        self.assertTrue(report.error)

    def test_incomplete_case_coverage_reports_error(self) -> None:
        partial = "import json,sys; json.load(sys.stdin); print(json.dumps({'cases': []}))"
        environ = {"MARCIANA_ADVERSARIAL_MEM0_CMD": f'{sys.executable} -c "{partial}"'}
        report = execute_external("mem0", "MARCIANA_ADVERSARIAL_MEM0_CMD", cases(), 1, environ)
        self.assertEqual(report.status, "error")


class SystemInventoryTests(unittest.TestCase):
    def test_all_systems_enumerated_never_substituted(self) -> None:
        suite = cases()
        selected = ("marciana",) + tuple(system for system, _ in EXTERNAL_SYSTEMS)
        reports = execute_systems(selected, suite, 1, {})
        self.assertEqual(tuple(report.system for report in reports), selected)
        self.assertIn("akka-fluree", {report.system for report in reports})
        statuses = {report.system: report.status for report in reports}
        self.assertEqual(statuses.pop("marciana"), "executed")
        self.assertTrue(all(status == "unavailable" for status in statuses.values()))

    def test_unknown_system_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            execute_systems(("marciana", "surprise"), cases(), 1, {})


class RecordedAdapterOutputTests(unittest.TestCase):
    def test_every_committed_output_is_complete_bounded_protocol_data(self) -> None:
        root = Path(__file__).resolve().parents[1]
        paths = sorted((root / "outputs").glob("*.json"))
        self.assertTrue(paths)
        suite = cases()
        for path in paths:
            payload = path.read_text(encoding="utf-8")
            _parse_external_outcomes(payload, suite)
            parsed = json.loads(payload)

            def assert_bounded(value) -> None:
                if isinstance(value, str):
                    self.assertLessEqual(len(value), 256, path.name)
                    self.assertNotIn("\n", value, path.name)
                elif isinstance(value, dict):
                    for key, item in value.items():
                        assert_bounded(key)
                        assert_bounded(item)
                elif isinstance(value, list):
                    for item in value:
                        assert_bounded(item)

            assert_bounded(parsed)


class LettaAppServerAdapterTests(unittest.TestCase):
    def test_uses_current_agent_sdk_without_claiming_adapter_routing_as_isolation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        package = json.loads(
            (root / "adapters/letta/package.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            package["dependencies"]["@letta-ai/letta-agent-sdk"], "0.6.2"
        )
        bridge = (root / "adapters/letta/bridge.js").read_text(encoding="utf-8")
        self.assertIn("LettaAgentClient", bridge)
        self.assertIn("client.prompt", bridge)
        self.assertIn("ollama/llama3.1:latest", bridge)
        self.assertNotIn("archive_id", bridge)

        tree = ast.parse(
            (root / "adapters/letta/adapter.py").read_text(encoding="utf-8")
        )
        assignment = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "capabilities"
                    for target in node.targets)
        )
        capabilities = ast.literal_eval(assignment.value.args[0])
        self.assertNotIn("isolation", capabilities)


if __name__ == "__main__":
    unittest.main()
