"""Tests for the v2 memory-store driver: identity-based authorization.

Three postures are exercised: a genuinely authenticating system (probe
passes, authorization cases run through system-issued tokens), a routing
system that claims isolation without an authentication surface (claims
stripped, cases declined), and a sham authenticator that accepts corrupted
credentials (probe fails, claims voided).
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters"))
sys.path.insert(0, str(ROOT / "tests"))

import protocol_v2
from protocol_v2 import AuthenticatedMemorySystem, prepare, run_v2
from test_protocol import MANIFEST, FakeSystem, MinimalSystem


class AuthFakeSystem(FakeSystem, AuthenticatedMemorySystem):
    """A FakeSystem whose principals are authenticated, not asserted.

    Credentials are issued by the system; operations receive opaque tokens
    which the system resolves internally — the adapter never interprets a
    principal name.
    """

    name = "auth-fake"
    authorization_mechanism = "fake-token-registry"

    def __init__(self) -> None:
        super().__init__()
        self._secrets = {
            name: f"secret-{name}"
            for name in ("operator", "analyst", "outsider", "advertiser")
        }
        self._tokens: dict[str, str] = {}

    def issued_credentials(self) -> dict[str, str]:
        return dict(self._secrets)

    def authenticate(self, name: str, secret: str) -> str | None:
        if self._secrets.get(name) != secret:
            return None
        token = f"tok:{name}"
        self._tokens[token] = name
        return token

    def _resolve(self, principal: str) -> str:
        # An unauthenticated token resolves to nobody: every check denies.
        return self._tokens.get(principal, "unauthenticated")

    def remember(self, memory_id, text, principal, **kwargs):
        return super().remember(memory_id, text, self._resolve(principal), **kwargs)

    def recall(self, query, principal, as_of=None):
        return super().recall(query, self._resolve(principal), as_of)

    def forget(self, memory_id, principal):
        return super().forget(memory_id, self._resolve(principal))

    def improve(self, memory_id, replacement_id, text, principal, *args):
        return super().improve(
            memory_id, replacement_id, text, self._resolve(principal), *args
        )


class ShamAuthSystem(AuthFakeSystem):
    """Claims authentication but accepts any credential — the probe's prey."""

    name = "sham-auth"

    def authenticate(self, name: str, secret: str) -> str | None:
        token = f"tok:{name}"
        self._tokens[token] = name
        return token


def drive_v2(system) -> dict:
    request = json.dumps({"protocol": "test", "repeats": 1, "cases": MANIFEST})
    stdout = io.StringIO()
    run_v2(system, stdin=io.StringIO(request), stdout=stdout)
    return json.loads(stdout.getvalue())


class PrepareTest(unittest.TestCase):
    def test_authenticated_system_passes_probe(self) -> None:
        view, capabilities, mechanism, check = prepare(AuthFakeSystem())
        self.assertEqual(check, "passed")
        self.assertIn("isolation", capabilities)
        self.assertEqual(mechanism, "fake-token-registry")

    def test_routing_system_strips_authorization_claims(self) -> None:
        view, capabilities, mechanism, check = prepare(MinimalSystem())
        self.assertEqual(check, "stripped-unauthenticated")
        self.assertNotIn("isolation", capabilities)
        self.assertEqual(mechanism, "none")

    def test_no_claims_is_not_applicable(self) -> None:
        class Plain(MinimalSystem):
            capabilities = frozenset({"retrieval", "persistence"})
        view, capabilities, mechanism, check = prepare(Plain())
        self.assertEqual(check, "not-applicable")

    def test_sham_authenticator_fails_probe(self) -> None:
        view, capabilities, mechanism, check = prepare(ShamAuthSystem())
        self.assertEqual(check, "failed-negative-probe")
        self.assertNotIn("isolation", capabilities)


class RunV2Test(unittest.TestCase):
    def test_authenticated_run_exercises_isolation_via_tokens(self) -> None:
        payload = drive_v2(AuthFakeSystem())
        self.assertEqual(payload["authorization_check"], "passed")
        self.assertEqual(payload["authorization_mechanism"], "fake-token-registry")
        rows = {row["case_id"]: row for row in payload["cases"]}
        self.assertTrue(rows["isolation-tenant"]["supported"])
        self.assertTrue(rows["isolation-tenant"]["correct"])
        self.assertTrue(rows["isolation-clearance"]["correct"])

    def test_routing_system_declines_isolation_in_v2(self) -> None:
        payload = drive_v2(MinimalSystem())
        self.assertEqual(payload["authorization_check"], "stripped-unauthenticated")
        rows = {row["case_id"]: row for row in payload["cases"]}
        self.assertFalse(rows["isolation-tenant"]["supported"])
        # Non-authorization capability is untouched.
        self.assertTrue(rows["order-invariant"]["supported"])

    def test_sham_authenticator_is_voided_and_flagged(self) -> None:
        payload = drive_v2(ShamAuthSystem())
        self.assertEqual(payload["authorization_check"], "failed-negative-probe")
        rows = {row["case_id"]: row for row in payload["cases"]}
        for case_id in ("isolation-tenant", "isolation-clearance", "purpose-denial"):
            self.assertFalse(rows[case_id]["supported"], case_id)


if __name__ == "__main__":
    unittest.main()
