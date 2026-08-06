"""Tests for the shared OSS adapter scenario driver."""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))

import protocol
from protocol import CAPABILITIES, MemorySystem, REQUIREMENTS, Unsupported

TOKEN = re.compile(r"[a-z0-9]+")
MANIFEST = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "marciana-adversarial-v1"
     / "manifest.json").read_text()
)["manifest"]["cases"]


def digest_of(memory_id: str) -> str:
    return "sha256:" + hashlib.sha256(memory_id.encode()).hexdigest()


class FakeSystem(MemorySystem):
    """An in-memory system claiming every capability the driver knows."""

    name = "fake"
    version = "1"
    capabilities = CAPABILITIES

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.rows: dict[str, dict] = {}
        self.nonces: set[str] = set()
        self.idempotency: dict[str, bool] = {}

    def remember(self, memory_id, text, principal, valid_from=None,
                 valid_until=None, private=False, nonce=None, supersedes=None,
                 derived_from=()) -> bool:
        if nonce is not None:
            if nonce in self.nonces:
                return False
            self.nonces.add(nonce)
        if len(text) > 4_096:
            return False
        self.rows[memory_id] = {
            "text": text, "owner": principal, "private": private,
            "valid_from": valid_from, "valid_until": valid_until,
            "derived_from": tuple(derived_from), "gone": False,
        }
        return True

    def _visible(self, row: dict, principal: str) -> bool:
        if row["gone"]:
            return False
        if principal in ("outsider", "advertiser"):
            return False
        if row["private"]:
            return row["owner"] == "operator" and principal == "operator"
        return principal in ("operator", "analyst") or row["owner"] == principal

    def recall(self, query, principal, as_of=None):
        if len(query) > 4_096:
            raise ValueError("oversized")
        words = frozenset(TOKEN.findall(query.lower()))
        ranked = []
        for memory_id, row in self.rows.items():
            if not self._visible(row, principal):
                continue
            if as_of is not None:
                if row["valid_from"] and row["valid_from"] > as_of:
                    continue
                if row["valid_until"] and as_of >= row["valid_until"]:
                    continue
            score = len(words & frozenset(TOKEN.findall(row["text"].lower())))
            if score:
                ranked.append((-score, memory_id))
        ranked.sort()
        return tuple(memory_id for _, memory_id in ranked)

    def forget(self, memory_id, principal):
        row = self.rows.get(memory_id)
        if row is None or principal != "operator":
            return False
        row["gone"] = True
        for other in self.rows.values():
            if memory_id in other["derived_from"]:
                other["gone"] = True
        return True

    def improve(self, memory_id, replacement_id, text, principal,
                expected_source_digest, idempotency_key):
        if idempotency_key in self.idempotency:
            return self.idempotency[idempotency_key]
        current = self.rows.get(memory_id)
        accepted = (current is not None and not current["gone"]
                    and expected_source_digest == digest_of(memory_id))
        if accepted:
            current["gone"] = True
            self.rows[replacement_id] = {
                "text": text, "owner": principal, "private": False,
                "valid_from": date(2026, 2, 1), "valid_until": None,
                "derived_from": (), "gone": False,
            }
        self.idempotency[idempotency_key] = accepted
        return accepted

    def restart(self) -> None:
        pass  # state is already durable in-process


class MinimalSystem(FakeSystem):
    name = "minimal"
    capabilities = frozenset({"retrieval", "isolation", "persistence"})


def drive(system: MemorySystem) -> list[dict]:
    request = json.dumps({"protocol": "test", "repeats": 1, "cases": MANIFEST})
    sys.stdin = io.StringIO(request)
    try:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            protocol.run(system)
    finally:
        sys.stdin = sys.__stdin__
    return json.loads(buffer.getvalue())["cases"]


class ProtocolTests(unittest.TestCase):
    def test_every_case_has_requirements_and_a_scenario(self) -> None:
        ids = {case["case_id"] for case in MANIFEST}
        self.assertEqual(ids, set(REQUIREMENTS))
        scenarios = protocol._scenarios(FakeSystem(), temporal=True)
        self.assertEqual(ids, set(scenarios))

    def test_fully_capable_system_passes_every_case(self) -> None:
        rows = drive(FakeSystem())
        self.assertEqual(len(rows), len(MANIFEST))
        for row in rows:
            with self.subTest(row["case_id"]):
                self.assertTrue(row["supported"])
                self.assertTrue(row["correct"], row)

    def test_minimal_system_declares_unsupported_honestly(self) -> None:
        rows = {row["case_id"]: row for row in drive(MinimalSystem())}
        unsupported = {case_id for case_id, row in rows.items() if not row["supported"]}
        self.assertEqual(unsupported, {
            "retrieval-current", "temporal-history", "abstain-unknown",
            "isolation-clearance", "purpose-denial", "forged-source",
            "stale-proposal", "replay-mutation", "replay-restart",
            "idempotent-retry", "forget-derived",
        })
        for case_id, row in rows.items():
            if row["supported"]:
                self.assertTrue(row["correct"], row)

    def test_unsupported_cases_report_no_results(self) -> None:
        rows = drive(MinimalSystem())
        for row in rows:
            if not row["supported"]:
                self.assertFalse(row["returned_ids"])
                self.assertFalse(row["correct"])


if __name__ == "__main__":
    unittest.main()
