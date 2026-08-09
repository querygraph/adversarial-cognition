"""Tests for v2 authenticated identities and the authenticated reference.

The invariant under test: authorization attributes live server-side, keyed by
an authenticated identity. A caller cannot mint a credential, cannot assert an
attribute, and a corrupted credential is rejected before any policy check.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adversarial_cognition.backend_v2 import AuthenticatedBackend
from adversarial_cognition.identity import IdentityRecord, IdentityRegistry

NOW = date(2026, 2, 1)


def fresh() -> AuthenticatedBackend:
    backend = AuthenticatedBackend()
    backend.seed()
    return backend


class IdentityRegistryTest(unittest.TestCase):
    def test_registered_identity_authenticates(self) -> None:
        registry = IdentityRegistry()
        credential = registry.register(IdentityRecord("did:key:operator", clearance=3))
        session = registry.authenticate("did:key:operator", credential)
        self.assertIsNotNone(session)
        self.assertEqual(session.record.clearance, 3)

    def test_forged_credential_denied(self) -> None:
        registry = IdentityRegistry()
        registry.register(IdentityRecord("did:key:operator", clearance=3))
        self.assertIsNone(registry.authenticate("did:key:operator", "0" * 64))

    def test_unregistered_identity_denied(self) -> None:
        registry = IdentityRegistry()
        self.assertIsNone(registry.authenticate("did:key:ghost", "0" * 64))

    def test_credential_for_one_identity_rejected_for_another(self) -> None:
        registry = IdentityRegistry()
        operator = registry.register(IdentityRecord("did:key:operator", clearance=3))
        registry.register(IdentityRecord("did:key:analyst", clearance=1))
        self.assertIsNone(registry.authenticate("did:key:analyst", operator))


class AuthenticatedBackendTest(unittest.TestCase):
    def test_operator_reads_private_memory(self) -> None:
        backend = fresh()
        credential = backend.credentials["did:key:operator"]
        decision = backend.recall(
            "private farm price", "did:key:operator", credential, NOW, "n-1"
        )
        self.assertTrue(decision.allowed)
        self.assertIn("private-farm", decision.ids)

    def test_under_cleared_analyst_never_sees_private(self) -> None:
        backend = fresh()
        credential = backend.credentials["did:key:analyst"]
        decision = backend.recall(
            "private farm price", "did:key:analyst", credential, NOW, "n-2"
        )
        self.assertNotIn("private-farm", decision.ids)

    def test_caller_cannot_assert_attributes(self) -> None:
        # The only inputs are (did, credential): there is no API through which
        # a caller can supply a tenant or clearance. Presenting the analyst's
        # credential yields the analyst's server-side record, whatever the
        # caller wishes it were.
        backend = fresh()
        credential = backend.credentials["did:key:analyst"]
        session = backend.authenticate("did:key:analyst", credential)
        self.assertEqual(session.record.clearance, 1)
        self.assertEqual(session.record.tenant, "agstack")

    def test_forged_credential_denied_before_policy(self) -> None:
        backend = fresh()
        decision = backend.recall(
            "coffee price", "did:key:operator", "f" * 64, NOW, "n-3"
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.error, "authentication-denied")
        self.assertEqual(decision.ids, ())

    def test_outsider_tenant_isolated(self) -> None:
        backend = fresh()
        credential = backend.credentials["did:key:outsider"]
        decision = backend.recall(
            "coffee price", "did:key:outsider", credential, NOW, "n-4"
        )
        self.assertEqual(decision.ids, ())

    def test_credentials_survive_restart(self) -> None:
        backend = fresh()
        credential = backend.credentials["did:key:operator"]
        backend.restart()
        decision = backend.recall(
            "coffee price", "did:key:operator", credential, NOW, "n-5"
        )
        self.assertTrue(decision.allowed)

    def test_deterministic_credentials_across_instances(self) -> None:
        # Receipts must be reproducible across identical runs, so credential
        # derivation is deterministic per benchmark key.
        self.assertEqual(
            AuthenticatedBackend().credentials, AuthenticatedBackend().credentials
        )


if __name__ == "__main__":
    unittest.main()
