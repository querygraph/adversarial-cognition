"""Deterministic policy-aware backend used by MARCIANA-ADVERSARIAL-v1."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import date

TOKEN = re.compile(r"[a-z0-9]+")
MAX_QUERY_CHARS = 4_096
MAX_TEXT_CHARS = 4_096


@dataclass(frozen=True)
class Actor:
    did: str
    tenant: str = "agstack"
    space: str = "coffee"
    purpose: str = "market-research"
    clearance: int = 1
    can_mutate: bool = True


@dataclass(frozen=True)
class Memory:
    memory_id: str
    text: str
    source: str
    source_digest: str
    tenant: str = "agstack"
    space: str = "coffee"
    sensitivity: int = 1
    valid_from: date = date(2026, 1, 1)
    valid_until: date | None = None
    state: str = "current"
    derived_from: tuple[str, ...] = ()
    purpose: str = "market-research"


@dataclass(frozen=True)
class Decision:
    allowed: bool
    ids: tuple[str, ...] = ()
    error: str = ""
    receipt: str = ""


def digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def words(value: str) -> frozenset[str]:
    return frozenset(TOKEN.findall(value.lower()))


class AdversarialBackend:
    """A small model of the TypeSec/Marciana authority boundary.

    The benchmark intentionally models only security-relevant semantics. It is
    not a replacement for the Rust vault or a production storage backend.
    """

    def __init__(self) -> None:
        self.memories: dict[str, Memory] = {}
        self.nonces: set[tuple[str, str]] = set()
        self.idempotency: dict[str, Decision] = {}

    def seed(self) -> None:
        self.remember(
            Memory(
                "price-old",
                "Honduras coffee price was 3.80 USD per kg at San Pedro Sula",
                "dataverse:coffee:2025-12",
                digest("price-old"),
                valid_from=date(2025, 1, 1),
                valid_until=date(2026, 1, 1),
            ),
            Actor("did:key:operator"),
            nonce="seed-old",
        )
        self.remember(
            Memory(
                "price-current",
                "Honduras coffee price is 4.20 USD per kg at San Pedro Sula",
                "dataverse:coffee:2026-01",
                digest("price-current"),
            ),
            Actor("did:key:operator"),
            nonce="seed-current",
        )
        self.remember(
            Memory(
                "private-farm",
                "Private farm price is 9.00 USD per kg",
                "private:farm-7",
                digest("private-farm"),
                sensitivity=3,
            ),
            Actor("did:key:operator", clearance=3),
            nonce="seed-private",
        )
        self.remember(
            Memory(
                "soil",
                "Honduras coffee farms use volcanic soil at high altitude",
                "agstack:soil",
                digest("soil"),
            ),
            Actor("did:key:operator"),
            nonce="seed-soil",
        )

    def _claim(self, actor: Actor, nonce: str) -> bool:
        key = (actor.did, nonce)
        if key in self.nonces:
            return False
        self.nonces.add(key)
        return True

    def _authorized(self, memory: Memory, actor: Actor) -> bool:
        return (
            memory.tenant == actor.tenant
            and memory.space == actor.space
            and memory.sensitivity <= actor.clearance
            and memory.purpose == actor.purpose
        )

    def remember(self, memory: Memory, actor: Actor, nonce: str) -> Decision:
        if not self._claim(actor, nonce) or not actor.can_mutate:
            return Decision(False, error="replay-or-mutation-denied")
        if len(memory.text) > MAX_TEXT_CHARS:
            return Decision(False, error="oversized-memory")
        if memory.tenant != actor.tenant or memory.space != actor.space:
            return Decision(False, error="scope-denied")
        if memory.sensitivity > actor.clearance:
            return Decision(False, error="clearance-denied")
        self.memories[memory.memory_id] = memory
        receipt = digest(f"remember:{memory.memory_id}:{memory.source_digest}")
        return Decision(True, (memory.memory_id,), receipt=receipt)

    def recall(self, query: str, actor: Actor, as_of: date, nonce: str) -> Decision:
        if not self._claim(actor, nonce):
            return Decision(False, error="replay")
        if len(query) > MAX_QUERY_CHARS:
            return Decision(False, error="oversized-query")
        query_words = words(query)
        ranked: list[tuple[int, str]] = []
        for memory in self.memories.values():
            if memory.state != "current" or not self._authorized(memory, actor):
                continue
            if memory.valid_from > as_of or (
                memory.valid_until is not None and as_of >= memory.valid_until
            ):
                continue
            score = len(query_words & words(memory.text))
            if score:
                ranked.append((score, memory.memory_id))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return Decision(True, tuple(item[1] for item in ranked), receipt=digest(f"recall:{ranked}"))

    def improve(
        self,
        memory_id: str,
        replacement: Memory,
        actor: Actor,
        nonce: str,
        expected_source_digest: str,
        idempotency_key: str,
    ) -> Decision:
        if not self._claim(actor, nonce) or not actor.can_mutate:
            return Decision(False, error="replay-or-mutation-denied")
        if idempotency_key in self.idempotency:
            return self.idempotency[idempotency_key]
        current = self.memories.get(memory_id)
        if current is None or current.source_digest != expected_source_digest:
            return Decision(False, error="stale-source")
        if not self._authorized(current, actor) or replacement.sensitivity > actor.clearance:
            return Decision(False, error="authorization-denied")
        self.memories[memory_id] = replace(current, state="superseded")
        self.memories[replacement.memory_id] = replacement
        receipt = digest(f"improve:{memory_id}:{replacement.memory_id}")
        decision = Decision(True, (memory_id, replacement.memory_id), receipt=receipt)
        self.idempotency[idempotency_key] = decision
        return decision

    def forget(self, memory_id: str, actor: Actor, nonce: str) -> Decision:
        if not self._claim(actor, nonce) or not actor.can_mutate:
            return Decision(False, error="replay-or-mutation-denied")
        memory = self.memories.get(memory_id)
        if memory is None or not self._authorized(memory, actor):
            return Decision(False, error="authorization-denied")
        self.memories[memory_id] = replace(memory, state="forgotten")
        for key, value in tuple(self.memories.items()):
            if memory_id in value.derived_from:
                self.memories[key] = replace(value, state="forgotten")
        return Decision(True, (memory_id,), receipt=digest(f"forget:{memory_id}"))

    def restart(self) -> "AdversarialBackend":
        # Nonce and idempotency state is durable: replay protection and retry
        # stability must survive a process restart, not only a warm session.
        restarted = AdversarialBackend()
        restarted.memories = dict(self.memories)
        restarted.nonces = set(self.nonces)
        restarted.idempotency = dict(self.idempotency)
        return restarted
