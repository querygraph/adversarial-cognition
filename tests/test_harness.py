"""Tests for the controlled agent-memory harness — no Ollama required.

A scripted fake transport plays the model: the loop, tool dispatch, budget
enforcement, bounded parsing, the driver's expressibility and capability
gating, the negative-credential probe, and the attestation block are all
exercised deterministically.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.agent_backends.marciana_agent import MarcianaAgentBackend
from adapters.agent_backends.memfs_agent import MemFSAgentBackend
from agent_harness.driver import EXPRESSIBLE_CASES, run
from agent_harness.tools import Credential
from agent_harness.loop import (
    MAX_TRANSCRIPT_CHARS,
    MAX_TURNS,
    LoopResult,
    parse_final,
    run_operation,
)
from agent_harness.prompts import PROMPT_DIGEST
from adversarial_cognition.cases import cases

SUITE = cases()
REQUEST = json.dumps({
    "protocol": "marciana-adversarial-adapter-v1",
    "repeats": 1,
    "cases": [
        {
            "case_id": case.case_id,
            "category": case.category,
            "description": case.description,
            "expected_allowed": case.expected_allowed,
            "expected_ids": list(case.expected_ids),
            "must_abstain": case.must_abstain,
            "forbidden_ids": list(case.forbidden_ids),
        }
        for case in SUITE
    ],
})


def obedient_model(messages, tools, options):
    """A minimal faithful model: read once, then answer with the tool's ids.

    Turn 1: call memory_read with the query from the user prompt (and the
    as_of date when the prompt carries one). For a delete task, call
    memory_delete on the named id. Turn 2: reply with the ids the tool
    returned, as a JSON array.
    """

    user = next(m["content"] for m in messages if m["role"] == "user")
    tool_results = [m for m in messages if m["role"] == "tool"]
    if not tool_results:
        if "memory_delete" in user or "delete the memory" in user:
            target = user.split('"')[1]
            return {"message": {"content": "", "tool_calls": [
                {"function": {"name": "memory_delete", "arguments": {"id": target}}},
            ]}}
        query = user.split("Query:", 1)[1].strip() if "Query:" in user else ""
        arguments = {"query": query}
        if "valid on" in user:
            arguments["as_of"] = user.split("valid on ", 1)[1].split(".", 1)[0]
        return {"message": {"content": "", "tool_calls": [
            {"function": {"name": "memory_read", "arguments": arguments}},
        ]}}
    payload = json.loads(tool_results[-1]["content"])
    ids = payload.get("ids", [])
    return {"message": {"content": json.dumps(ids)}}


class ParseFinalTest(unittest.TestCase):
    def test_parses_json_array(self) -> None:
        self.assertEqual(parse_final('["a", "b"]'), ("a", "b"))

    def test_bounds_count_and_length(self) -> None:
        ids = parse_final(json.dumps([f"id-{i}" * 40 for i in range(20)]))
        self.assertEqual(len(ids), 8)
        self.assertTrue(all(len(item) <= 64 for item in ids))

    def test_unparseable_is_abstention(self) -> None:
        self.assertEqual(parse_final("the answer is price-current"), ())
        self.assertEqual(parse_final('{"ids": ["a"]}'), ())

    def test_prose_wrapped_array_recovered(self) -> None:
        self.assertEqual(parse_final('Here you go: ["x"]'), ("x",))


class LoopTest(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = MemFSAgentBackend()
        self.backend.reset()
        self.session = self.backend.open_session(Credential("operator", ""))

    def test_tool_call_then_answer(self) -> None:
        self.backend.write(self.session, "fact", "coffee price data")
        result = run_operation(
            obedient_model, self.backend, self.session,
            "Task: find matching ids. Query: coffee price",
        )
        self.assertEqual(result.ids, ("fact",))
        self.assertEqual(result.turns, 2)

    def test_turn_cap_is_budget_exceeded(self) -> None:
        def looping_model(messages, tools, options):
            return {"message": {"content": "", "tool_calls": [
                {"function": {"name": "memory_list", "arguments": {}}},
            ]}}
        result = run_operation(looping_model, self.backend, self.session, "loop")
        self.assertTrue(result.budget_exceeded)
        self.assertEqual(result.turns, MAX_TURNS)
        self.assertEqual(result.ids, ())

    def test_transcript_budget_enforced(self) -> None:
        result = run_operation(
            obedient_model, self.backend, self.session,
            "Query: " + "x" * (MAX_TRANSCRIPT_CHARS + 1),
        )
        self.assertTrue(result.budget_exceeded)

    def test_transport_failure_is_recorded(self) -> None:
        def broken(messages, tools, options):
            raise ConnectionError("ollama down")
        result = run_operation(broken, self.backend, self.session, "Query: x")
        self.assertEqual(result.ids, ())
        self.assertIn("ollama down", result.error)

    def test_malformed_tool_arguments_do_not_crash(self) -> None:
        calls = {"n": 0}
        def malformed(messages, tools, options):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"message": {"content": "", "tool_calls": [
                    {"function": {"name": "memory_read", "arguments": "not json"}},
                ]}}
            return {"message": {"content": "[]"}}
        result = run_operation(malformed, self.backend, self.session, "Query: x")
        self.assertEqual(result.ids, ())


class DriverTest(unittest.TestCase):
    def run_driver(self, backend) -> dict:
        stdout = io.StringIO()
        run(backend, obedient_model, stdin=io.StringIO(REQUEST), stdout=stdout)
        return json.loads(stdout.getvalue())

    def test_marciana_agent_full_replay(self) -> None:
        payload = self.run_driver(MarcianaAgentBackend())
        self.assertEqual(payload["interface"], "agent-loop")
        self.assertEqual(payload["harness"]["prompt_digest"], PROMPT_DIGEST)
        self.assertEqual(payload["authorization_check"], "passed")
        rows = {row["case_id"]: row for row in payload["cases"]}
        self.assertEqual(len(rows), len(SUITE))
        # Inexpressible cases are unsupported for the whole track.
        for case_id in ("oversized-query", "replay-mutation", "order-invariant"):
            self.assertFalse(rows[case_id]["supported"], case_id)
        # The reference holds every expressible case under an obedient model.
        for case_id in EXPRESSIBLE_CASES:
            self.assertTrue(rows[case_id]["supported"], case_id)
            self.assertTrue(rows[case_id]["correct"], case_id)

    def test_memfs_declines_authorization_cases(self) -> None:
        payload = self.run_driver(MemFSAgentBackend())
        rows = {row["case_id"]: row for row in payload["cases"]}
        for case_id in ("isolation-tenant", "isolation-clearance",
                        "purpose-denial", "confusable-query",
                        "injection-contained", "temporal-history"):
            self.assertFalse(rows[case_id]["supported"], case_id)
        self.assertEqual(payload["authorization_mechanism"], "none")
        # No authorization capability claimed → the probe is not applicable.
        self.assertEqual(payload["authorization_check"], "not-applicable")
        self.assertTrue(rows["retrieval-current"]["supported"])

    def test_negative_probe_voids_routing_adapter(self) -> None:
        class RoutingBackend(MemFSAgentBackend):
            # Claims isolation but authenticates nothing: the exact
            # adapter-supplied-boundary pattern the probe exists to catch.
            capabilities = MemFSAgentBackend.capabilities | frozenset(
                {"isolation", "clearance", "purpose"}
            )
            def provision(self):
                return {"operator": "s1", "analyst": "s2",
                        "outsider": "s3", "advertiser": "s4"}
            def open_session(self, credential):
                return credential.name  # accepts anything, even corrupted

        payload = self.run_driver(RoutingBackend())
        self.assertEqual(payload["authorization_check"], "failed-negative-probe")
        rows = {row["case_id"]: row for row in payload["cases"]}
        for case_id in ("isolation-tenant", "isolation-clearance",
                        "purpose-denial"):
            self.assertFalse(rows[case_id]["supported"], case_id)


if __name__ == "__main__":
    unittest.main()
