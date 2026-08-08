"""Deterministic reference model of a capability-secured authority boundary.

This is to CAPABILITY-ADVERSARIAL-v1 what the reference catalog is to the
catalog-provenance benchmark: a small, dependency-free model of the
security-relevant semantics TypeSec provides, so every case has one correct
outcome and the whole suite runs in milliseconds. It is not TypeSec's Rust
implementation and does not replace it; it defines, in executable form, what a
*capability-gated authority* must guarantee.

The model covers TypeSec's signature properties as they behave at run time:

- a capability is minted only by the policy engine and is **unforgeable** — it
  carries a seal only the engine can produce, so a hand-crafted capability is
  refused (the runtime shadow of TypeSec's compile-time constructor privacy);
- **attenuation is monotonic** — a derived capability can only narrow: it can
  drop grants and shorten its lease, never widen a permission or extend a lease;
- a capability is bound to **one resource instance**, not a resource type;
- **revocation** (by id, and by epoch for a mid-lease ``revoke_all``) and
  **lease expiry** make a capability stop authorizing, provably;
- **reveal / declassify are gated** on an information-flow label: a read below
  the caller's clearance is redacted, and lowering a label needs an explicit
  declassify grant;
- a model tool-call is **deny-by-default** — it runs only when backed by a
  presented, valid capability, defeating ambient authority and the confused
  deputy;
- every authorization decision emits a **durable audit** event, and a request
  carrying unknown/injected fields is refused at the wire.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field, replace

DOMAIN = "querygraph.capability-adversarial.v1"
# The engine's minting secret. Only code holding this key can produce a valid
# capability seal; that is what makes a capability unforgeable at run time.
_ENGINE_KEY = b"capability-adversarial/reference-engine-key/v1"

# Information-flow clearance lattice: public < internal < sensitive. A read is
# authorized only when the capability carries a read grant at or above the
# value's label.
LEVELS = ("public", "internal", "sensitive")

# The set of fields an authorization request may carry. Anything else is a
# smuggled field and the request is refused at the wire.
REQUEST_FIELDS = frozenset({"subject", "grants", "resource", "operation", "lease"})


def digest(*parts: object) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256((DOMAIN + "\0" + payload).encode()).hexdigest()


def _level(label: str) -> int:
    return LEVELS.index(label)


def _read_ceiling(grants: tuple[str, ...]) -> int:
    """The highest label these grants may read, or -1 if none."""
    best = -1
    for g in grants:
        if g.startswith("read:") and g[5:] in LEVELS:
            best = max(best, _level(g[5:]))
    return best


def _grant_implied(parent, g: str) -> bool:
    """Is grant ``g`` no broader than what ``parent`` already holds? Read grants
    obey the clearance lattice — holding ``read:sensitive`` implies the right to
    ``read:internal`` — so attenuating a read to a lower level is allowed. Every
    other grant is atomic and must be held outright."""
    if g.startswith("read:") and g[5:] in LEVELS:
        return _read_ceiling(tuple(parent)) >= _level(g[5:])
    return g in parent


@dataclass(frozen=True)
class Capability:
    """An unforgeable, attenuable authority to act on one resource instance."""

    cap_id: str
    subject: str
    grants: tuple[str, ...]     # sorted atomic grants, e.g. read:sensitive, tool:search
    resource: str               # the exact resource *instance*, never a type
    operation: str              # the operation/job this authority was minted for
    expiry: int                 # logical-clock time at which the lease ends
    epoch: int                  # minting epoch; a later revoke_all invalidates it
    seal: str = ""

    def _body(self) -> tuple:
        return (self.cap_id, self.subject, tuple(self.grants), self.resource,
                self.operation, self.expiry, self.epoch)

    def sealed(self, key: bytes) -> "Capability":
        payload = json.dumps(("cap",) + self._body(), sort_keys=True).encode()
        mac = hmac.new(key, DOMAIN.encode() + b"\0" + payload, hashlib.sha256).hexdigest()
        return replace(self, seal="hmac:" + mac)


@dataclass(frozen=True)
class SecureValue:
    """Labeled data. Its cleartext is only reachable through ``reveal``."""

    label: str          # one of LEVELS
    cleartext: str
    resource: str

    def __repr__(self) -> str:  # never echo the cleartext
        return f"SecureValue(label={self.label!r}, resource={self.resource!r}, <redacted>)"


REDACTED = "<redacted>"


@dataclass(frozen=True)
class Outcome:
    ok: bool
    error: str = ""
    capability: Capability | None = None
    revealed: str | None = None
    audit_present: bool = False


class Guard:
    """A model of TypeSec's capability-gated authority boundary.

    Durable state (the revocation list, the epoch, the audit log) survives
    ``restart`` — revocation and audit are durability properties, not
    warm-cache conveniences. A logical clock (``now``) drives lease expiry so
    the model is fully deterministic.
    """

    name = "reference"
    version = "capability-adversarial-v1"

    def __init__(self) -> None:
        # policy[subject] -> set of grants that subject may be minted, per resource.
        self.policy: dict[str, dict[str, frozenset[str]]] = {}
        self.revoked: set[str] = set()        # capability ids explicitly revoked
        self.min_epoch: int = 0               # revoke_all raises this
        self.now: int = 0                     # logical clock
        self.audit: list[str] = []
        self._n: int = 0                      # monotone id counter (deterministic)

    # -- setup -----------------------------------------------------------
    def grant_policy(self, subject: str, resource: str, grants: frozenset[str]) -> None:
        self.policy.setdefault(subject, {})[resource] = frozenset(grants)

    def tick(self, n: int = 1) -> None:
        self.now += n

    def _next_id(self) -> str:
        self._n += 1
        return f"cap-{self._n:04d}"

    def _audit(self, kind: str, **fields: object) -> None:
        # Evidence carries a digest of the decision, never raw payloads.
        self.audit.append(digest("audit", kind, fields))

    # -- verification ----------------------------------------------------
    def verify(self, cap: Capability | None) -> bool:
        """A capability authorizes only if its seal is intact, it has not been
        revoked (by id or by epoch), and its lease has not expired."""
        if cap is None:
            return False
        if cap.sealed(_ENGINE_KEY).seal != cap.seal:
            return False                       # forged or tampered
        if cap.cap_id in self.revoked:
            return False                       # revoked by id
        if cap.epoch < self.min_epoch:
            return False                       # revoked by epoch (revoke_all)
        if self.now >= cap.expiry:
            return False                       # lease expired
        return True

    # -- minting & attenuation ------------------------------------------
    def mint(self, subject: str, grants: frozenset[str], resource: str,
             operation: str, lease: int) -> Outcome:
        """Mint a capability iff policy authorizes every requested grant for
        this subject on this exact resource. A denied mint yields no authority."""
        allowed = self.policy.get(subject, {}).get(resource, frozenset())
        if not frozenset(grants) <= allowed:
            self._audit("mint-denied", subject=subject, resource=resource)
            return Outcome(False, "policy-denied", audit_present=True)
        cap = Capability(
            cap_id=self._next_id(), subject=subject, grants=tuple(sorted(grants)),
            resource=resource, operation=operation, expiry=self.now + lease,
            epoch=self.min_epoch).sealed(_ENGINE_KEY)
        self._audit("mint", cap_id=cap.cap_id, subject=subject, resource=resource)
        return Outcome(True, capability=cap, audit_present=True)

    def attenuate(self, cap: Capability, grants: frozenset[str] | None = None,
                  lease: int | None = None) -> Outcome:
        """Derive a strictly-narrower capability. The engine refuses to widen a
        permission or extend a lease — attenuation is monotone by construction."""
        if not self.verify(cap):
            return Outcome(False, "invalid-parent")
        new_grants = frozenset(cap.grants if grants is None else grants)
        if not all(_grant_implied(cap.grants, g) for g in new_grants):
            self._audit("attenuate-denied", reason="widen")
            return Outcome(False, "permission-widened", audit_present=True)
        new_expiry = cap.expiry if lease is None else self.now + lease
        if new_expiry > cap.expiry:
            self._audit("attenuate-denied", reason="extend")
            return Outcome(False, "lease-extended", audit_present=True)
        derived = Capability(
            cap_id=self._next_id(), subject=cap.subject,
            grants=tuple(sorted(new_grants)), resource=cap.resource,
            operation=cap.operation, expiry=new_expiry,
            epoch=cap.epoch).sealed(_ENGINE_KEY)
        self._audit("attenuate", parent=cap.cap_id, cap_id=derived.cap_id)
        return Outcome(True, capability=derived, audit_present=True)

    # -- revocation ------------------------------------------------------
    def revoke(self, cap_id: str) -> None:
        self.revoked.add(cap_id)
        self._audit("revoke", cap_id=cap_id)

    def revoke_all(self) -> None:
        self.min_epoch += 1
        self._audit("revoke-all", epoch=self.min_epoch)

    # -- guarded operations ---------------------------------------------
    def reveal(self, cap: Capability | None, value: SecureValue) -> Outcome:
        """Reveal labeled data. Requires a valid capability bound to the exact
        resource with a read grant at or above the value's label; otherwise the
        content is redacted — never disclosed."""
        if not self.verify(cap) or cap.resource != value.resource:
            self._audit("reveal-refused", resource=value.resource)
            return Outcome(False, "unauthorized", revealed=REDACTED, audit_present=True)
        if _read_ceiling(cap.grants) < _level(value.label):
            self._audit("reveal-redacted", resource=value.resource, label=value.label)
            return Outcome(False, "below-clearance", revealed=REDACTED, audit_present=True)
        self._audit("reveal", cap_id=cap.cap_id, resource=value.resource)
        return Outcome(True, revealed=value.cleartext, audit_present=True)

    def declassify(self, cap: Capability | None, value: SecureValue) -> Outcome:
        """Lower a value's label. Requires an explicit ``declassify`` grant;
        without it the label cannot be lowered."""
        if not self.verify(cap) or cap.resource != value.resource:
            return Outcome(False, "unauthorized", audit_present=False)
        if "declassify" not in cap.grants:
            self._audit("declassify-refused", resource=value.resource)
            return Outcome(False, "no-declassify-grant", audit_present=True)
        self._audit("declassify", cap_id=cap.cap_id, resource=value.resource)
        return Outcome(True, audit_present=True)

    def invoke(self, cap: Capability | None, tool: str, resource: str,
               operation: str) -> Outcome:
        """A model tool-call. Deny-by-default: it runs only when backed by a
        valid capability carrying the matching ``tool:`` grant, bound to the
        exact resource and operation. Ambient calls (no capability) are refused,
        and a capability for one operation cannot drive another."""
        if not self.verify(cap):
            self._audit("invoke-denied", tool=tool, reason="no-capability")
            return Outcome(False, "ambient-denied", audit_present=True)
        if cap.resource != resource:
            self._audit("invoke-denied", tool=tool, reason="resource")
            return Outcome(False, "cross-resource", audit_present=True)
        if f"tool:{tool}" not in cap.grants or cap.operation != operation:
            self._audit("invoke-denied", tool=tool, reason="confused-deputy")
            return Outcome(False, "confused-deputy", audit_present=True)
        self._audit("invoke", cap_id=cap.cap_id, tool=tool, resource=resource)
        return Outcome(True, audit_present=True)

    def request(self, payload: dict) -> Outcome:
        """Accept an authorization request off the wire. Any field outside the
        known set is a smuggled field and the request is refused before it can
        reach the policy engine."""
        extra = set(payload) - REQUEST_FIELDS
        if extra:
            self._audit("wire-rejected", fields=sorted(extra))
            return Outcome(False, "unknown-fields", audit_present=True)
        return self.mint(
            subject=payload["subject"], grants=frozenset(payload["grants"]),
            resource=payload["resource"], operation=payload.get("operation", ""),
            lease=int(payload.get("lease", 100)))

    def restart(self) -> "Guard":
        fresh = Guard()
        fresh.policy = {s: dict(r) for s, r in self.policy.items()}
        fresh.revoked = set(self.revoked)
        fresh.min_epoch = self.min_epoch
        fresh.now = self.now
        fresh.audit = list(self.audit)
        fresh._n = self._n
        return fresh
