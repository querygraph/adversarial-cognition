"""Deterministic reference model of a provable-transaction catalog.

This is to CATALOG-PROVENANCE-v1 what the reference vault is to the cognition
benchmark: a small, dependency-free model of the security- and
provenance-relevant semantics a governed Iceberg catalog must provide. It is
not LakeCat's Rust implementation and does not replace it; it defines, in
executable form, what a *provable* transaction is, so every case has one
correct outcome and the whole suite runs in milliseconds.

The model covers the signature LakeCat properties: optimistic concurrency
(compare-and-swap on the metadata pointer), idempotent commit replay, a
durable audit trail and an outbox staged atomically with the commit, receipts
that verify offline and chain to their predecessor, governed-scan
authorization receipts bound to policy digests, tombstone receipts, and the
invariant that evidence carries digests — never plaintext locations or
secrets.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace

DOMAIN = "querygraph.catalog-provenance.v1"
MAX_TEXT = 4_096


def digest(*parts: object) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256((DOMAIN + "\0" + payload).encode()).hexdigest()


def policy_digest(policy: str) -> str:
    # A policy hash is the digest of the governing ODRL policy text; a scan is
    # only authorized against the exact policy it was planned under.
    return "sha256:" + hashlib.sha256(("policy\0" + policy).encode()).hexdigest()


@dataclass(frozen=True)
class Receipt:
    """An offline-verifiable record of one accepted table transition."""

    table: str
    op: str                    # commit | tombstone
    previous_metadata: str     # digest of the pointer this transition asserted
    new_metadata: str          # digest of the pointer it advanced to
    snapshot_id: int
    principal: str
    policy_hash: str
    idempotency_key: str
    request_hash: str
    response_hash: str
    prev_receipt: str          # receipt hash of the predecessor, or "" for head
    receipt_hash: str = ""

    def sealed(self) -> "Receipt":
        body = (self.table, self.op, self.previous_metadata, self.new_metadata,
                self.snapshot_id, self.principal, self.policy_hash,
                self.idempotency_key, self.request_hash, self.response_hash,
                self.prev_receipt)
        return replace(self, receipt_hash=digest("receipt", *body))

    def verifies(self) -> bool:
        return self.sealed().receipt_hash == self.receipt_hash


@dataclass(frozen=True)
class ScanReceipt:
    """A governed-scan authorization receipt bound to the exact read policy."""

    table: str
    principal: str
    policy_hashes: tuple[str, ...]
    snapshot_id: int
    receipt_hash: str = ""

    def sealed(self) -> "ScanReceipt":
        return replace(self, receipt_hash=digest(
            "scan", self.table, self.principal, tuple(self.policy_hashes), self.snapshot_id))

    def verifies(self, expected_policy_hashes: tuple[str, ...]) -> bool:
        # The scan is authorized only if its bound policy set matches exactly
        # and the receipt digest is intact.
        return (bool(self.policy_hashes)
                and tuple(self.policy_hashes) == tuple(expected_policy_hashes)
                and self.sealed().receipt_hash == self.receipt_hash)


@dataclass(frozen=True)
class Outcome:
    ok: bool
    error: str = ""
    receipt: Receipt | None = None
    scan_receipt: ScanReceipt | None = None
    audit_present: bool = False
    outbox_present: bool = False
    lineage_present: bool = False


@dataclass
class _Table:
    metadata: str
    snapshot_id: int
    head_receipt: str
    tombstoned: bool = False


class ReferenceCatalog:
    """A model of a governed Iceberg catalog with provable transactions.

    Durable state (tables, idempotency records, audit, outbox, receipts)
    survives ``restart`` — replay protection and offline verification are
    durability properties, not warm-cache conveniences.
    """

    name = "reference"
    version = "catalog-provenance-v1"

    def __init__(self) -> None:
        self.tables: dict[str, _Table] = {}
        self.idempotency: dict[str, Outcome] = {}
        self.audit: list[str] = []
        self.outbox: list[str] = []
        self.lineage: list[str] = []
        self.receipts: dict[str, Receipt] = {}

    # -- helpers ---------------------------------------------------------
    def _bad_text(self, *values: str) -> bool:
        return any(len(v) > MAX_TEXT for v in values)

    def pointer(self, table: str) -> str:
        entry = self.tables.get(table)
        return entry.metadata if entry else ""

    def create(self, table: str, principal: str) -> Outcome:
        meta = digest("meta", table, 0)
        self.tables[table] = _Table(meta, 0, "")
        return Outcome(True)

    def commit(self, table: str, expected_metadata: str, update: str,
               principal: str, policy: str, nonce: str,
               idempotency_key: str) -> Outcome:
        if self._bad_text(update, policy):
            return Outcome(False, "oversized")
        if idempotency_key and idempotency_key in self.idempotency:
            # Exact idempotent retry: return the stored result, no new effect.
            return self.idempotency[idempotency_key]
        entry = self.tables.get(table)
        if entry is None or entry.tombstoned:
            return Outcome(False, "no-such-table")
        if expected_metadata != entry.metadata:
            # Compare-and-swap: a stale assertion loses; nothing is written,
            # and — crucially — no audit/outbox/lineage evidence is emitted.
            return Outcome(False, "stale-metadata")

        new_snapshot = entry.snapshot_id + 1
        new_meta = digest("meta", table, new_snapshot, update)
        req_hash = digest("request", table, expected_metadata, update, nonce)
        resp_hash = digest("response", table, new_meta, new_snapshot)
        receipt = Receipt(
            table=table, op="commit", previous_metadata=expected_metadata,
            new_metadata=new_meta, snapshot_id=new_snapshot, principal=principal,
            policy_hash=policy_digest(policy), idempotency_key=idempotency_key,
            request_hash=req_hash, response_hash=resp_hash,
            prev_receipt=entry.head_receipt).sealed()

        # One atomic transition: advance the pointer and stage every piece of
        # evidence together. If the receipt is not produced, none of it is.
        entry.metadata = new_meta
        entry.snapshot_id = new_snapshot
        entry.head_receipt = receipt.receipt_hash
        self.receipts[receipt.receipt_hash] = receipt
        self.audit.append(digest("audit", receipt.receipt_hash))
        self.outbox.append(digest("outbox", receipt.receipt_hash))
        self.lineage.append(digest("lineage", receipt.receipt_hash))

        outcome = Outcome(True, receipt=receipt, audit_present=True,
                          outbox_present=True, lineage_present=True)
        if idempotency_key:
            self.idempotency[idempotency_key] = outcome
        return outcome

    def scan(self, table: str, principal: str, policy: str) -> Outcome:
        entry = self.tables.get(table)
        if entry is None or entry.tombstoned:
            return Outcome(False, "no-such-table")
        receipt = ScanReceipt(
            table=table, principal=principal,
            policy_hashes=(policy_digest(policy),),
            snapshot_id=entry.snapshot_id).sealed()
        return Outcome(True, scan_receipt=receipt)

    def tombstone(self, table: str, principal: str, policy: str,
                  nonce: str) -> Outcome:
        entry = self.tables.get(table)
        if entry is None or entry.tombstoned:
            return Outcome(False, "no-such-table")
        req_hash = digest("request", table, "drop", nonce)
        receipt = Receipt(
            table=table, op="tombstone", previous_metadata=entry.metadata,
            new_metadata=digest("meta", table, "tombstone"),
            snapshot_id=entry.snapshot_id, principal=principal,
            policy_hash=policy_digest(policy), idempotency_key="",
            request_hash=req_hash, response_hash=digest("response", "dropped"),
            prev_receipt=entry.head_receipt).sealed()
        entry.tombstoned = True
        entry.head_receipt = receipt.receipt_hash
        self.receipts[receipt.receipt_hash] = receipt
        self.audit.append(digest("audit", receipt.receipt_hash))
        self.outbox.append(digest("outbox", receipt.receipt_hash))
        return Outcome(True, receipt=receipt, audit_present=True,
                       outbox_present=True)

    def replay(self, receipt: Receipt) -> bool:
        # Offline verification: the receipt must be internally consistent AND
        # be the one this catalog durably recorded.
        return receipt.verifies() and receipt.receipt_hash in self.receipts

    def restart(self) -> "ReferenceCatalog":
        fresh = ReferenceCatalog()
        fresh.tables = {k: replace(v) for k, v in self.tables.items()}
        fresh.idempotency = dict(self.idempotency)
        fresh.audit = list(self.audit)
        fresh.outbox = list(self.outbox)
        fresh.lineage = list(self.lineage)
        fresh.receipts = dict(self.receipts)
        return fresh
