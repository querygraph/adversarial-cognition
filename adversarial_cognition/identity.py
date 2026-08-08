"""Authenticated identities for MARCIANA-ADVERSARIAL-v2.

v1's reference accepted a caller-built ``Actor`` whose tenant, clearance, and
purpose were asserted by the caller — exactly the pattern v2 bans (an adapter
that supplies the boundary is credited with an isolation the system does not
enforce). v2 moves every authorization attribute server-side: an identity is
registered with the backend, the backend issues an HMAC credential for it, and
every operation authenticates that credential before the registry record — not
anything the caller asserts — feeds the authorization predicate.

HMAC (stdlib) rather than signatures: the core forbids third-party
dependencies, and HMAC makes the invariant fully testable — a caller cannot
mint a credential, cannot alter a registered attribute, and a corrupted
credential is rejected by ``authenticate``. The key is fixed per benchmark so
receipts remain deterministic across identical runs.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from hashlib import sha256

BENCHMARK_IDENTITY_KEY = b"marciana-adversarial-v2-identity"


@dataclass(frozen=True)
class IdentityRecord:
    """Server-side authorization attributes bound to an identity."""

    did: str
    tenant: str = "agstack"
    space: str = "coffee"
    purpose: str = "market-research"
    clearance: int = 1
    can_mutate: bool = True


@dataclass(frozen=True)
class Session:
    """Proof of a successful authentication; wraps the registry record."""

    record: IdentityRecord


class IdentityRegistry:
    """Registers identities and authenticates credentials against them."""

    def __init__(self, key: bytes = BENCHMARK_IDENTITY_KEY) -> None:
        self._key = key
        self._records: dict[str, IdentityRecord] = {}

    def register(self, record: IdentityRecord) -> str:
        """Register an identity and return its credential."""

        self._records[record.did] = record
        return self._credential(record.did)

    def _credential(self, did: str) -> str:
        return hmac.new(self._key, did.encode("utf-8"), sha256).hexdigest()

    def authenticate(self, did: str, credential: str) -> Session | None:
        """Return a session only for a registered identity's own credential."""

        record = self._records.get(did)
        if record is None:
            return None
        if not hmac.compare_digest(self._credential(did), credential):
            return None
        return Session(record)

    def records(self) -> tuple[IdentityRecord, ...]:
        return tuple(self._records.values())
