"""Tests for the deterministic adversarial backend's authority semantics."""

from __future__ import annotations

import unittest
from datetime import date

from adversarial_cognition.backend import Actor, AdversarialBackend, Memory, digest

OPERATOR = Actor("did:key:operator")
AS_OF = date(2026, 2, 1)


def seeded() -> AdversarialBackend:
    backend = AdversarialBackend()
    backend.seed()
    return backend


def fact(memory_id: str, text: str = "spot fact", **overrides: object) -> Memory:
    return Memory(memory_id, text, "test", digest(memory_id), **overrides)


class BackendAuthorizationTests(unittest.TestCase):
    def test_recall_denies_by_scope_clearance_and_purpose(self) -> None:
        backend = seeded()
        table = (
            ("tenant", Actor("did:key:outsider", tenant="rival")),
            ("space", Actor("did:key:operator", space="cocoa")),
            ("clearance", Actor("did:key:analyst", clearance=0)),
            ("purpose", Actor("did:key:operator", purpose="advertising")),
        )
        for label, actor in table:
            with self.subTest(label):
                decision = backend.recall("Honduras coffee price", actor, AS_OF, f"nonce-{label}")
                self.assertTrue(decision.allowed)
                self.assertEqual(decision.ids, ())

    def test_remember_denies_scope_and_clearance(self) -> None:
        backend = seeded()
        denied = backend.remember(fact("other", tenant="rival"), OPERATOR, "n1")
        self.assertEqual(denied.error, "scope-denied")
        denied = backend.remember(fact("secret", sensitivity=3), OPERATOR, "n2")
        self.assertEqual(denied.error, "clearance-denied")

    def test_read_only_actor_cannot_mutate(self) -> None:
        backend = seeded()
        reader = Actor("did:key:reader", can_mutate=False)
        self.assertFalse(backend.remember(fact("f"), reader, "n1").allowed)
        self.assertFalse(backend.forget("price-current", reader, "n2").allowed)


class BackendTemporalTests(unittest.TestCase):
    def test_valid_time_window_selects_the_right_fact(self) -> None:
        backend = seeded()
        past = backend.recall("Honduras coffee price", OPERATOR, date(2025, 6, 1), "past")
        self.assertEqual(past.ids[:1], ("price-old",))
        current = backend.recall("Honduras coffee price", OPERATOR, AS_OF, "now")
        self.assertEqual(current.ids[:1], ("price-current",))
        self.assertNotIn("price-old", current.ids)

    def test_before_any_validity_returns_nothing(self) -> None:
        backend = seeded()
        decision = backend.recall("Honduras coffee price", OPERATOR, date(2024, 1, 1), "early")
        self.assertEqual(decision.ids, ())


class BackendMutationTests(unittest.TestCase):
    def improvement(self) -> Memory:
        return fact("price-improved", "price now 4.60 USD per kg", valid_from=AS_OF)

    def test_forged_source_digest_rejected(self) -> None:
        backend = seeded()
        decision = backend.improve(
            "price-current", self.improvement(), OPERATOR, "n1", digest("wrong"), "job"
        )
        self.assertEqual(decision.error, "stale-source")

    def test_idempotent_retry_returns_identical_decision(self) -> None:
        backend = seeded()
        first = backend.improve(
            "price-current", self.improvement(), OPERATOR, "n1", digest("price-current"), "job"
        )
        retry = backend.restart().improve(
            "price-current", self.improvement(), OPERATOR, "n2", digest("price-current"), "job"
        )
        self.assertTrue(first.allowed)
        self.assertEqual(first, retry)

    def test_nonce_replay_rejected_even_after_restart(self) -> None:
        backend = seeded()
        self.assertTrue(backend.remember(fact("a"), OPERATOR, "nonce").allowed)
        warm = backend.remember(fact("b"), OPERATOR, "nonce")
        cold = backend.restart().remember(fact("c"), OPERATOR, "nonce")
        self.assertEqual(warm.error, "replay-or-mutation-denied")
        self.assertEqual(cold.error, "replay-or-mutation-denied")


class BackendForgetTests(unittest.TestCase):
    def test_forget_cascades_to_derived_memories(self) -> None:
        backend = seeded()
        backend.remember(
            fact("summary", "derived summary of coffee price", derived_from=("price-current",)),
            OPERATOR,
            "derive",
        )
        self.assertTrue(backend.forget("price-current", OPERATOR, "forget").allowed)
        recalled = backend.restart().recall("coffee price summary", OPERATOR, AS_OF, "after")
        self.assertNotIn("price-current", recalled.ids)
        self.assertNotIn("summary", recalled.ids)


class BackendRobustnessTests(unittest.TestCase):
    def test_oversized_inputs_rejected(self) -> None:
        backend = seeded()
        query = backend.recall("q" * 5_000, OPERATOR, AS_OF, "big-query")
        self.assertEqual(query.error, "oversized-query")
        memory = backend.remember(fact("big", "x" * 5_000), OPERATOR, "big-memory")
        self.assertEqual(memory.error, "oversized-memory")

    def test_identical_recalls_produce_identical_receipts(self) -> None:
        first = seeded().recall("volcanic soil", OPERATOR, AS_OF, "r1")
        second = seeded().recall("volcanic soil", OPERATOR, AS_OF, "r2")
        self.assertEqual(first.receipt, second.receipt)
        self.assertEqual(first.ids, second.ids)


if __name__ == "__main__":
    unittest.main()
