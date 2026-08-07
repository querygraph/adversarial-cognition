# Appendix D — The capability gates and cases

CAPABILITY-ADVERSARIAL-v1 counts safety failures in ten hard gates, under the
same constitution as the other two benchmarks: any nonzero gate fails the
release, and a gate trips only on a capability a system claimed. On the recorded
run, every gate held at zero for all ten systems.

1. **`unauthorized_mint`** — the engine minted a capability the policy forbids.
2. **`forged_capability_accepted`** — a capability with an invalid or absent
   seal was honored.
3. **`permission_widened`** — a derived capability carried a broader grant than
   its parent.
4. **`lease_extended`** — a derived capability outlived its parent's lease.
5. **`cross_resource_reveal`** — a capability acted on a resource instance it
   was not bound to.
6. **`revoked_capability_honored`** — a revoked or expired capability authorized
   an action.
7. **`label_leaked`** — labeled data was disclosed above clearance, or
   declassified without the grant.
8. **`ambient_tool_call_executed`** — a tool call ran with no backing
   capability.
9. **`confused_deputy_exploited`** — authority for one operation drove another.
10. **`injected_field_accepted`** — a request carrying unknown fields was
    accepted.

The eighteen cases, by capability:

| # | Case | Capability | The expectation |
|---|---|---|---|
| 1 | `mint-authorized` | mint-capability | An authorized subject mints a capability, with audit |
| 2 | `mint-denied-by-policy` | mint-capability | A policy-denied mint yields no capability at all |
| 3 | `forged-capability-rejected` | mint-capability | A capability with a tampered seal is refused |
| 4 | `attenuate-narrows` | attenuation-monotonic | Attenuation drops grants and shortens the lease |
| 5 | `widen-permission-rejected` | attenuation-monotonic | Attenuation cannot widen a permission |
| 6 | `extend-lease-rejected` | attenuation-monotonic | Attenuation cannot extend a lease |
| 7 | `resource-instance-bound` | resource-instance-binding | A capability reveals its bound resource instance |
| 8 | `cross-resource-rejected` | resource-instance-binding | A capability for one instance cannot act on another |
| 9 | `revoke-by-id` | revocation | A capability revoked by id stops authorizing |
| 10 | `revoke-all-epoch` | revocation | Revoke-all invalidates outstanding capabilities mid-lease |
| 11 | `lease-expiry-enforced` | lease-expiry | A capability past its lease is inactive |
| 12 | `reveal-authorized` | reveal-gating | A matching read capability reveals the cleartext |
| 13 | `reveal-below-clearance-redacted` | reveal-gating | A read below clearance is redacted, not disclosed |
| 14 | `declassify-requires-grant` | declassify-gating | Lowering a label needs an explicit declassify grant |
| 15 | `ambient-tool-call-denied` | deny-by-default-tool | A tool call with no capability is refused |
| 16 | `confused-deputy-rejected` | confused-deputy-resistance | Authority for one operation cannot drive another |
| 17 | `audit-on-every-decision` | audit-on-decision | Both allow and deny leave a durable audit event |
| 18 | `wire-injected-field-rejected` | wire-integrity | A request with a smuggled field is refused |

Recorded results (2026-08-06, every adapter live over its system's real
library): the reference holds 18 of 18; TypeSec 17 of 17 claimed (declining
`wire-integrity`, which the capability core has no request wire to claim);
Biscuit 8, Macaroons 6, and UCAN 3 in the capability-token band; JWT 6 at the
bearer floor; Cedar, OPA, OpenFGA, and SpiceDB 4 each in the decision band.
Every system held every capability it claimed; all gates zero across the field.
