"""Authenticated reference backend for MARCIANA-ADVERSARIAL-v2.

Wraps the deterministic v1 policy core behind authenticated sessions: every
operation takes a ``(did, credential)`` pair, authenticates it against the
server-side identity registry, and builds the authorization actor from the
registry record alone. There is no API through which a caller can assert a
tenant, clearance, or purpose — the v2 statement of "the adapter enforces no
gate" for the reference itself.

The v1 ``AdversarialBackend`` and its callers are untouched; v1 remains the
frozen, published benchmark.
"""

from __future__ import annotations

from datetime import date

from .backend import Actor, AdversarialBackend, Decision, Memory
from .identity import IdentityRecord, IdentityRegistry, Session

DENIED = Decision(False, error="authentication-denied")

# The four benchmark principals, registered server-side. The operator owns the
# seeded space including the private memory; the analyst shares tenant and
# purpose but is under-cleared; the outsider is a foreign tenant; the
# advertiser carries a mismatched purpose.
PRINCIPALS = (
    IdentityRecord("did:key:operator", clearance=3),
    IdentityRecord("did:key:analyst", clearance=1),
    IdentityRecord("did:key:outsider", tenant="rival"),
    IdentityRecord("did:key:advertiser", purpose="advertising"),
)


class AuthenticatedBackend:
    """The v2 reference: the v1 policy core behind authenticated identities."""

    def __init__(self) -> None:
        self.core = AdversarialBackend()
        self.identities = IdentityRegistry()
        self.credentials: dict[str, str] = {
            record.did: self.identities.register(record) for record in PRINCIPALS
        }

    def seed(self) -> None:
        self.core.seed()

    def restart(self) -> None:
        # Identities are durable: registrations and credentials survive a
        # restart exactly as nonces and idempotency keys do in the core.
        self.core = self.core.restart()

    def authenticate(self, did: str, credential: str) -> Session | None:
        return self.identities.authenticate(did, credential)

    def _actor(self, session: Session) -> Actor:
        record = session.record
        return Actor(
            did=record.did,
            tenant=record.tenant,
            space=record.space,
            purpose=record.purpose,
            clearance=record.clearance,
            can_mutate=record.can_mutate,
        )

    def remember(
        self, memory: Memory, did: str, credential: str, nonce: str
    ) -> Decision:
        session = self.authenticate(did, credential)
        if session is None:
            return DENIED
        return self.core.remember(memory, self._actor(session), nonce)

    def recall(
        self, query: str, did: str, credential: str, as_of: date, nonce: str
    ) -> Decision:
        session = self.authenticate(did, credential)
        if session is None:
            return DENIED
        return self.core.recall(query, self._actor(session), as_of, nonce)

    def improve(
        self,
        memory_id: str,
        replacement: Memory,
        did: str,
        credential: str,
        nonce: str,
        expected_source_digest: str,
        idempotency_key: str,
    ) -> Decision:
        session = self.authenticate(did, credential)
        if session is None:
            return DENIED
        return self.core.improve(
            memory_id, replacement, self._actor(session), nonce,
            expected_source_digest, idempotency_key,
        )

    def forget(self, memory_id: str, did: str, credential: str, nonce: str) -> Decision:
        session = self.authenticate(did, credential)
        if session is None:
            return DENIED
        return self.core.forget(memory_id, self._actor(session), nonce)
