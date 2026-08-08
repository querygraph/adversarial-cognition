"""Shared scenario driver for real-catalog adapters.

An adapter implements :class:`CatalogSystem` for its catalog and declares which
provable-transaction capabilities that catalog *enforces*. The driver replays
each benchmark case behaviorally and scores only the cases whose capability the
catalog claims; anything else is reported ``supported: false`` — the catalog is
measured on what it backs, never on a boundary it never claimed. A method a
catalog cannot express raises :class:`Unsupported`, which is also reported as
unsupported rather than failed.

The interface mirrors the reference catalog so that a real Iceberg REST catalog
maps onto it naturally: ``create``/``commit`` are the standard REST commit path
(``compare-and-swap`` is Iceberg's requirement-guarded ``updateTable``), while
the governance methods (audit, outbox, replay, governed scan, receipt chain,
tombstone) correspond to endpoints only a governed catalog exposes.
"""

from __future__ import annotations

import json
import sys


class Unsupported(Exception):
    """Raised by a method whose catalog genuinely cannot express it."""


class CatalogSystem:
    name = "unnamed"
    version = "unversioned"
    capabilities: frozenset[str] = frozenset()

    def reset(self) -> None:
        raise NotImplementedError

    # -- commit path (standard Iceberg REST) -----------------------------
    def create(self, table: str) -> None:
        raise NotImplementedError

    def pointer(self, table: str) -> str:
        """An opaque token identifying the table's current committed state."""
        raise NotImplementedError

    def commit(self, table: str, expected: str, update: str,
               idempotency_key: str = "") -> dict:
        """Commit against ``expected`` state. Return a dict with at least
        ``ok`` (bool) and, when the catalog provides it, ``receipt``. A
        compare-and-swap violation returns ``{"ok": False, ...}`` rather than
        raising."""
        raise NotImplementedError

    # -- governance surfaces (a governed catalog only) -------------------
    def audit_count(self) -> int:
        raise Unsupported("durable audit")

    def outbox_count(self) -> int:
        raise Unsupported("atomic outbox")

    def lineage_count(self) -> int:
        raise Unsupported("lineage evidence")

    def replay(self, receipt: dict) -> bool:
        raise Unsupported("replayable proof")

    def scan(self, table: str, policy: str) -> dict:
        raise Unsupported("governed scan proof")

    def scan_verifies(self, scan_receipt: dict, policy: str) -> bool:
        raise Unsupported("governed scan proof")

    def tombstone(self, table: str) -> dict:
        raise Unsupported("tombstone proof")

    def evidence_blobs(self) -> list[str]:
        raise Unsupported("hash-only evidence")

    def restart(self) -> None:
        raise Unsupported("restart")


POLICY = "read allowed for purpose analytics"
SECRET = "s3://warehouse/secret-location/AKIAEXAMPLE"


def _scenarios(sys_: CatalogSystem):
    T = "sales.events"

    def _fresh_commit(update="u", key=""):
        return sys_.commit(T, sys_.pointer(T), update, key)

    def commit_fresh() -> bool:
        before = sys_.pointer(T)
        out = _fresh_commit()
        return bool(out.get("ok")) and sys_.pointer(T) != before

    def cas_stale_rejected() -> bool:
        head = sys_.pointer(T)
        first = sys_.commit(T, head, "a")
        stale = sys_.commit(T, head, "b")  # still asserts the old head
        return bool(first.get("ok")) and not stale.get("ok")

    def cas_concurrent() -> bool:
        head = sys_.pointer(T)
        a = sys_.commit(T, head, "a")
        b = sys_.commit(T, head, "b")
        return bool(a.get("ok")) != bool(b.get("ok"))  # exactly one wins

    def idempotent_retry() -> bool:
        head = sys_.pointer(T)
        first = sys_.commit(T, head, "u", "job-k")
        after = sys_.pointer(T)
        second = sys_.commit(T, head, "u", "job-k")
        return (first.get("ok") and second.get("ok")
                and first.get("receipt") == second.get("receipt")
                and sys_.pointer(T) == after)

    def idempotent_across_restart() -> bool:
        head = sys_.pointer(T)
        first = sys_.commit(T, head, "u", "job-k")
        sys_.restart()
        second = sys_.commit(T, head, "u", "job-k")
        return first.get("ok") and second.get("ok") and first.get("receipt") == second.get("receipt")

    def audit_durable() -> bool:
        n = sys_.audit_count()
        out = _fresh_commit()
        return bool(out.get("ok")) and sys_.audit_count() == n + 1

    def outbox_present() -> bool:
        n = sys_.outbox_count()
        out = _fresh_commit()
        return bool(out.get("ok")) and sys_.outbox_count() == n + 1

    def outbox_absent_on_reject() -> bool:
        head = sys_.pointer(T)
        sys_.commit(T, head, "a")
        n = sys_.outbox_count()
        sys_.commit(T, head, "b")  # stale → rejected
        return sys_.outbox_count() == n

    def replay_verifies() -> bool:
        out = _fresh_commit()
        return bool(out.get("ok")) and sys_.replay(out["receipt"])

    def replay_forged_rejected() -> bool:
        out = _fresh_commit()
        forged = dict(out["receipt"])
        forged["response_hash"] = "sha256:" + "0" * 64
        return bool(out.get("ok")) and not sys_.replay(forged)

    def governed_scan_receipt() -> bool:
        _fresh_commit()
        out = sys_.scan(T, POLICY)
        return bool(out.get("ok")) and sys_.scan_verifies(out["scan_receipt"], POLICY)

    def governed_scan_mismatch_rejected() -> bool:
        out = sys_.scan(T, POLICY)
        return bool(out.get("ok")) and not sys_.scan_verifies(out["scan_receipt"], "other policy")

    def receipt_chain_linked() -> bool:
        a = _fresh_commit("u1")
        b = _fresh_commit("u2")
        return bool(a.get("ok")) and bool(b.get("ok")) and \
            b["receipt"].get("prev_receipt") == a["receipt"].get("receipt_hash")

    def tombstone_covered() -> bool:
        _fresh_commit()
        out = sys_.tombstone(T)
        return bool(out.get("ok")) and out.get("receipt", {}).get("op") == "tombstone"

    def hash_only_audit() -> bool:
        sys_.commit(T, sys_.pointer(T), SECRET)
        return all("AKIA" not in b and "secret-location" not in b for b in sys_.evidence_blobs())

    def lineage_emitted() -> bool:
        n = sys_.lineage_count()
        out = _fresh_commit()
        return bool(out.get("ok")) and sys_.lineage_count() == n + 1

    def restart_reproducible() -> bool:
        out = _fresh_commit()
        sys_.restart()
        return bool(out.get("ok")) and sys_.replay(out["receipt"])

    return {
        "commit-fresh": commit_fresh,
        "cas-stale-rejected": cas_stale_rejected,
        "cas-concurrent": cas_concurrent,
        "idempotent-retry": idempotent_retry,
        "idempotent-across-restart": idempotent_across_restart,
        "audit-durable": audit_durable,
        "outbox-atomic-present": outbox_present,
        "outbox-absent-on-reject": outbox_absent_on_reject,
        "replay-verifies": replay_verifies,
        "replay-forged-rejected": replay_forged_rejected,
        "governed-scan-receipt": governed_scan_receipt,
        "governed-scan-mismatch-rejected": governed_scan_mismatch_rejected,
        "receipt-chain-linked": receipt_chain_linked,
        "tombstone-covered": tombstone_covered,
        "hash-only-audit": hash_only_audit,
        "lineage-emitted": lineage_emitted,
        "restart-reproducible": restart_reproducible,
    }


def run(system: CatalogSystem) -> None:
    """Drive every requested case against the catalog and print the outcomes."""

    request = json.load(sys.stdin)
    scenarios = _scenarios(system)

    # Preflight: if the baseline commit path cannot even be exercised (a
    # connection or configuration failure), the catalog is reported `error` —
    # never as false safety-gate violations. This keeps a misconfigured adapter
    # from looking like a catalog that accepted a lost update.
    try:
        system.reset()
        system.create("sales.events")
        scenarios["commit-fresh"]()
    except Exception as error:  # noqa: BLE001
        sys.exit(f"preflight commit failed: {error}")

    rows = []
    for case in request["cases"]:
        case_id = case["case_id"]
        if case["capability"] not in system.capabilities:
            rows.append({"case_id": case_id, "supported": False, "correct": False})
            continue
        try:
            system.reset()
            system.create("sales.events")
            correct = bool(scenarios[case_id]())
            supported = True
        except Unsupported:
            correct, supported = False, False
        except Exception as error:  # noqa: BLE001 - a probe failure is an incorrect result, reported
            sys.stderr.write(f"{case_id}: {error}\n")
            correct, supported = False, True
        rows.append({"case_id": case_id, "supported": supported, "correct": correct})
    print(json.dumps({
        "adapter_version": f"{system.name}-{system.version}",
        "capabilities": sorted(system.capabilities),
        "cases": rows,
    }))
