"""The CAPABILITY-ADVERSARIAL-v1 case corpus, run against the reference guard.

Each case exercises one capability-security property behaviorally, with an
explicit expected outcome. The reference guard must pass every case; that is the
CI gate and the executable definition of "capability-gated authority."

Capabilities name what a system *enforces*; a comparison system that does not
claim a capability declares the case unsupported rather than being scored on it.
Gates are the zero-tolerance safety properties: any gate failure fails the
release, regardless of every other number.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

from .backend import Capability, Guard, SecureValue, REDACTED, _ENGINE_KEY

CORPUS_VERSION = "capability-adversarial-v1"

# What a system may claim to enforce.
CAPABILITIES = (
    "mint-capability",           # a capability is minted only by an authorizing policy engine
    "attenuation-monotonic",     # a derived capability only narrows: never widen, never extend
    "resource-instance-binding", # a capability authorizes one resource instance, not a type
    "revocation",                # a revoked capability stops authorizing, mid-lease
    "lease-expiry",              # a capability past its lease is inactive
    "reveal-gating",             # revealing labeled data needs a matching read capability
    "declassify-gating",         # lowering a label needs an explicit declassify grant
    "deny-by-default-tool",      # a model tool-call runs only when backed by a capability
    "confused-deputy-resistance",# authority for one operation cannot drive another
    "audit-on-decision",         # every authorization decision emits a durable audit event
    "wire-integrity",            # a request carrying unknown/injected fields is refused
)

# Safety gates: each maps to the case(s) whose failure trips it.
GATES = (
    "unauthorized_mint",           # the engine minted a capability the policy forbids
    "forged_capability_accepted",  # a capability with an invalid/absent seal was honored
    "permission_widened",          # a derived capability carried a broader grant than its parent
    "lease_extended",              # a derived capability outlived its parent's lease
    "cross_resource_reveal",       # a capability acted on a resource instance it wasn't bound to
    "revoked_capability_honored",  # a revoked or expired capability authorized an action
    "label_leaked",                # labeled data disclosed above clearance, or declassified ungranted
    "ambient_tool_call_executed",  # a tool-call ran with no backing capability
    "confused_deputy_exploited",   # authority for one operation drove another
    "injected_field_accepted",     # a request carrying unknown fields was accepted
)


@dataclass(frozen=True)
class Case:
    case_id: str
    category: str
    capability: str
    description: str
    run: Callable[[Guard], bool] = field(compare=False)
    gate: str = ""  # the safety gate this case guards, if any


# A conventional operator, a resource instance, and a sensitive value used
# across the corpus.
OP = "did:key:operator"
R2 = "customer/2"
R1 = "customer/1"


def _seeded() -> Guard:
    g = Guard()
    # The operator may hold a broad authority on customer/2; nothing on customer/1.
    g.grant_policy(OP, R2, frozenset({
        "read:sensitive", "read:internal", "read:public",
        "write", "declassify", "tool:search"}))
    # A limited analyst may only read internal on customer/2.
    g.grant_policy("did:key:analyst", R2, frozenset({"read:internal"}))
    return g


def _mint_ok(g: Guard, grants, resource=R2, operation="job-a", lease=100, subject=OP):
    out = g.mint(subject, frozenset(grants), resource, operation, lease)
    assert out.ok, out.error
    return out.capability


def cases() -> tuple[Case, ...]:
    def mint_authorized(g: Guard) -> bool:
        n = len(g.audit)
        out = g.mint(OP, frozenset({"read:sensitive"}), R2, "job-a", 100)
        return (out.ok and g.verify(out.capability)
                and out.audit_present and len(g.audit) == n + 1)

    def mint_denied_by_policy(g: Guard) -> bool:
        # The analyst is not granted write on customer/2 → no capability at all.
        out = g.mint("did:key:analyst", frozenset({"write"}), R2, "job-a", 100)
        return (not out.ok) and out.capability is None and out.error == "policy-denied"

    def forged_capability_rejected(g: Guard) -> bool:
        cap = _mint_ok(g, {"read:sensitive"})
        # Adversary widens the grant set and re-uses the old seal — a forgery.
        forged = replace(cap, grants=("read:sensitive", "write", "tool:search"))
        return (not g.verify(forged)
                and not g.invoke(forged, "search", R2, "job-a").ok)

    def attenuate_narrows(g: Guard) -> bool:
        cap = _mint_ok(g, {"read:sensitive", "write", "tool:search"}, lease=100)
        out = g.attenuate(cap, grants=frozenset({"read:internal"}), lease=10)
        d = out.capability
        return (out.ok and g.verify(d)
                and set(d.grants) == {"read:internal"}
                and d.expiry <= cap.expiry)

    def widen_permission_rejected(g: Guard) -> bool:
        cap = _mint_ok(g, {"read:internal"})
        # Requesting a grant the parent never held must be refused, not minted.
        out = g.attenuate(cap, grants=frozenset({"read:internal", "write"}))
        return (not out.ok) and out.capability is None and out.error == "permission-widened"

    def extend_lease_rejected(g: Guard) -> bool:
        cap = _mint_ok(g, {"read:internal"}, lease=10)
        out = g.attenuate(cap, lease=1000)  # longer than the parent lease
        return (not out.ok) and out.capability is None and out.error == "lease-extended"

    def resource_instance_bound(g: Guard) -> bool:
        cap = _mint_ok(g, {"read:internal"}, resource=R2)
        v = SecureValue("internal", "the-secret", R2)
        out = g.reveal(cap, v)
        return out.ok and out.revealed == "the-secret"

    def cross_resource_rejected(g: Guard) -> bool:
        cap = _mint_ok(g, {"read:internal"}, resource=R2)
        # Same type, different instance: a capability for customer/2 must not
        # reveal customer/1.
        v = SecureValue("internal", "other-customer-secret", R1)
        out = g.reveal(cap, v)
        return (not out.ok) and out.revealed == REDACTED

    def revoke_by_id(g: Guard) -> bool:
        cap = _mint_ok(g, {"read:internal"})
        v = SecureValue("internal", "s", R2)
        before = g.reveal(cap, v).ok
        g.revoke(cap.cap_id)
        after = g.reveal(cap, v)
        return before and (not after.ok) and after.revealed == REDACTED

    def revoke_all_epoch(g: Guard) -> bool:
        cap = _mint_ok(g, {"read:internal"}, lease=1000)
        v = SecureValue("internal", "s", R2)
        before = g.reveal(cap, v).ok
        g.revoke_all()                      # mid-lease: bumps the epoch
        after = g.reveal(cap, v)
        return before and (not after.ok)

    def lease_expiry_enforced(g: Guard) -> bool:
        cap = _mint_ok(g, {"read:internal"}, lease=5)
        v = SecureValue("internal", "s", R2)
        before = g.reveal(cap, v).ok
        g.tick(5)                           # advance past the lease
        after = g.reveal(cap, v)
        return before and (not after.ok)

    def reveal_authorized(g: Guard) -> bool:
        cap = _mint_ok(g, {"read:sensitive"})
        v = SecureValue("sensitive", "top-secret", R2)
        out = g.reveal(cap, v)
        return out.ok and out.revealed == "top-secret"

    def reveal_below_clearance_redacted(g: Guard) -> bool:
        cap = _mint_ok(g, {"read:internal"})       # cannot read sensitive
        v = SecureValue("sensitive", "top-secret", R2)
        out = g.reveal(cap, v)
        return (not out.ok) and out.revealed == REDACTED and out.error == "below-clearance"

    def declassify_requires_grant(g: Guard) -> bool:
        cap = _mint_ok(g, {"read:sensitive"})       # no declassify grant
        v = SecureValue("sensitive", "top-secret", R2)
        out = g.declassify(cap, v)
        return (not out.ok) and out.error == "no-declassify-grant"

    def ambient_tool_call_denied(g: Guard) -> bool:
        # A tool-call with no presented capability must be refused.
        out = g.invoke(None, "search", R2, "job-a")
        return (not out.ok) and out.error == "ambient-denied"

    def confused_deputy_rejected(g: Guard) -> bool:
        # A capability minted for job-a's search cannot drive a delete on job-b.
        cap = _mint_ok(g, {"tool:search"}, operation="job-a")
        out = g.invoke(cap, "delete", R2, "job-b")
        return (not out.ok) and out.error in ("confused-deputy",)

    def audit_on_every_decision(g: Guard) -> bool:
        n = len(g.audit)
        g.mint(OP, frozenset({"read:internal"}), R2, "job-a", 100)   # allow
        g.mint("did:key:analyst", frozenset({"write"}), R2, "job-a", 100)  # deny
        # Both the allow and the deny leave a durable audit event.
        return len(g.audit) == n + 2

    def wire_injected_field_rejected(g: Guard) -> bool:
        out = g.request({
            "subject": OP, "grants": ["read:internal"], "resource": R2,
            "operation": "job-a", "lease": 100,
            "shadow_grant": "write"})           # smuggled field
        return (not out.ok) and out.error == "unknown-fields"

    return (
        Case("mint-authorized", "mint", "mint-capability", "an authorized subject mints a capability, with audit", mint_authorized),
        Case("mint-denied-by-policy", "mint", "mint-capability", "a policy-denied mint yields no capability", mint_denied_by_policy, "unauthorized_mint"),
        Case("forged-capability-rejected", "mint", "mint-capability", "a capability with a tampered seal is refused", forged_capability_rejected, "forged_capability_accepted"),
        Case("attenuate-narrows", "attenuation", "attenuation-monotonic", "attenuation drops grants and shortens the lease", attenuate_narrows),
        Case("widen-permission-rejected", "attenuation", "attenuation-monotonic", "attenuation cannot widen a permission", widen_permission_rejected, "permission_widened"),
        Case("extend-lease-rejected", "attenuation", "attenuation-monotonic", "attenuation cannot extend a lease", extend_lease_rejected, "lease_extended"),
        Case("resource-instance-bound", "binding", "resource-instance-binding", "a capability reveals its bound resource instance", resource_instance_bound),
        Case("cross-resource-rejected", "binding", "resource-instance-binding", "a capability for one instance cannot act on another", cross_resource_rejected, "cross_resource_reveal"),
        Case("revoke-by-id", "revocation", "revocation", "a capability revoked by id stops authorizing", revoke_by_id, "revoked_capability_honored"),
        Case("revoke-all-epoch", "revocation", "revocation", "revoke_all invalidates outstanding capabilities mid-lease", revoke_all_epoch, "revoked_capability_honored"),
        Case("lease-expiry-enforced", "expiry", "lease-expiry", "a capability past its lease is inactive", lease_expiry_enforced, "revoked_capability_honored"),
        Case("reveal-authorized", "reveal", "reveal-gating", "a matching read capability reveals the cleartext", reveal_authorized),
        Case("reveal-below-clearance-redacted", "reveal", "reveal-gating", "a read below clearance is redacted, not disclosed", reveal_below_clearance_redacted, "label_leaked"),
        Case("declassify-requires-grant", "declassify", "declassify-gating", "lowering a label needs an explicit declassify grant", declassify_requires_grant, "label_leaked"),
        Case("ambient-tool-call-denied", "tool", "deny-by-default-tool", "a tool-call with no capability is refused", ambient_tool_call_denied, "ambient_tool_call_executed"),
        Case("confused-deputy-rejected", "tool", "confused-deputy-resistance", "authority for one operation cannot drive another", confused_deputy_rejected, "confused_deputy_exploited"),
        Case("audit-on-every-decision", "audit", "audit-on-decision", "both allow and deny leave a durable audit event", audit_on_every_decision),
        Case("wire-injected-field-rejected", "wire", "wire-integrity", "a request with a smuggled field is refused", wire_injected_field_rejected, "injected_field_accepted"),
    )


def run_case(case: Case) -> bool:
    return bool(case.run(_seeded()))
