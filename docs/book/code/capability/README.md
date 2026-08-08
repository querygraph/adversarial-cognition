# capability-adversarial

**CAPABILITY-ADVERSARIAL-v1** — an adversarial benchmark for capability-gated
authority. It does not ask whether a system *has* authorization; every agent
framework does. It asks whether the authority a system grants is one an attacker
— or the model itself — **cannot forge, cannot widen on delegation, cannot
replay past revocation, and cannot aim at the wrong resource.**

The system under test is [TypeSec](https://github.com/querygraph), the
capability layer of the QueryGraph stack: an unforgeable `Capability<P, R>`
minted only by a policy engine, attenuable only downward, bound to one resource
instance, revocable and leased, gating `reveal`/`declassify` on an
information-flow label, and deny-by-default on every model tool-call. It is
measured against the real field — capability tokens (UCAN, Biscuit, Macaroons),
a bearer floor (JWT/OAuth scopes), and policy engines (OPA, Cedar, SpiceDB,
OpenFGA).

## Release policy

Safety failures are counted in named **hard gates that must be zero** — never
averaged into a score:

`unauthorized_mint`, `forged_capability_accepted`, `permission_widened`,
`lease_extended`, `cross_resource_reveal`, `revoked_capability_honored`,
`label_leaked`, `ambient_tool_call_executed`, `confused_deputy_exploited`,
`injected_field_accepted`.

## Quick start

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -q   # the reference is the CI gate
python3 run_benchmark.py --systems reference              # → reports/capability-adversarial-v1.json
python3 render_results.py                                  # → out/RESULTS.md
```

The reference guard is a deterministic, dependency-free model of the
capability-gated boundary; it must pass every case with every gate at zero. Real
systems run behind adapters configured through
`CAPABILITY_ADVERSARIAL_<SYSTEM>_CMD` and speak a JSON protocol over stdio, the
same shape as the [catalog-provenance](https://github.com/querygraph/catalog-provenance)
benchmark.

## What it tests

Eighteen cases across eleven capabilities, each with one correct outcome:
minting under policy, monotone attenuation over an `Implies` lattice,
resource-instance binding, revocation (by id and by mid-lease epoch), lease
expiry, reveal/declassify gating on an information-flow label, deny-by-default
tool-calls, confused-deputy resistance, audit on every decision, and wire
integrity. See [`docs/CAPABILITY-ADVERSARIAL-v1.md`](docs/CAPABILITY-ADVERSARIAL-v1.md)
for the full threat model, capabilities, gates, and competitor matrix.

## License

MIT OR Apache-2.0.
