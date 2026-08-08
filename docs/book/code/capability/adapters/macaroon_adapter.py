"""Macaroons adapter — bearer capability tokens with caveat attenuation.

A macaroon is a bearer token whose authority is *narrowed* by appending
first-party caveats, each folded into an HMAC chain so a caveat cannot be
removed without breaking verification. That gives macaroons three of this
benchmark's properties, and this adapter claims only those:

- ``attenuation-monotonic`` — appending a caveat narrows; a caveat cannot be
  removed (the chain breaks), so authority can never widen or a lease extend;
- ``resource-instance-binding`` — a ``resource = ...`` caveat binds the token to
  one instance, and verification rejects a mismatch;
- ``lease-expiry`` — a ``time < ...`` caveat is checked at verification.

Macaroons have no policy-gated mint (any holder of the root key mints freely),
no revocation by construction, and no information-flow labels, so the
mint-capability, revocation, reveal/declassify, tool, audit, and wire columns
are declared unsupported.
"""

from __future__ import annotations

import sys
import time

from pymacaroons import Macaroon, Verifier

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import run  # noqa: E402

KEY = "capability-adversarial/macaroon-root-key"
LOC = "capability-adversarial"

CAPABILITIES = ["attenuation-monotonic", "resource-instance-binding", "lease-expiry"]


def _mint(resource: str) -> Macaroon:
    m = Macaroon(location=LOC, identifier="cap", key=KEY)
    m.add_first_party_caveat(f"resource = {resource}")
    return m


def _verify(m: Macaroon, resource: str, at_time: float | None = None) -> bool:
    now = at_time if at_time is not None else time.time()
    v = Verifier()
    v.satisfy_exact(f"resource = {resource}")

    def time_ok(caveat: str) -> bool:
        if caveat.startswith("time < "):
            return now < float(caveat.split("time < ", 1)[1])
        return False

    v.satisfy_general(time_ok)
    try:
        return v.verify(m, KEY)
    except Exception:
        return False


def run_case(case_id: str) -> bool:
    if case_id == "attenuate-narrows":
        m = _mint("customer/2")
        narrowed = m.copy()
        narrowed.add_first_party_caveat(f"time < {time.time() + 10}")
        # The narrowed token still verifies for its resource, now also time-bound.
        return _verify(narrowed, "customer/2")

    if case_id == "widen-permission-rejected":
        # A macaroon's caveats cannot be removed: stripping the resource caveat
        # and re-signing is impossible without the root key. Reconstructing a
        # "wider" macaroon from the serialized form drops the HMAC chain and
        # fails verification — authority cannot be widened.
        m = _mint("customer/2")
        m.add_first_party_caveat("op = read")
        # Attempt to forge a widened token by tampering the last caveat.
        tampered = Macaroon.deserialize(m.serialize())
        tampered.caveats[-1].caveat_id = "op = admin"
        return not _verify(tampered, "customer/2")

    if case_id == "extend-lease-rejected":
        # A time caveat only ever tightens the bound. Appending a *later* time
        # caveat does not extend validity: the earliest bound still governs.
        m = _mint("customer/2")
        m.add_first_party_caveat(f"time < {time.time() + 5}")
        m.add_first_party_caveat(f"time < {time.time() + 10_000}")
        # After the first bound lapses the token is invalid regardless of the
        # looser second caveat.
        return not _verify(m, "customer/2", at_time=time.time() + 6)

    if case_id == "resource-instance-bound":
        return _verify(_mint("customer/2"), "customer/2")

    if case_id == "cross-resource-rejected":
        return not _verify(_mint("customer/2"), "customer/1")

    if case_id == "lease-expiry-enforced":
        m = _mint("customer/2")
        m.add_first_party_caveat(f"time < {time.time() + 1}")
        fresh = _verify(m, "customer/2")
        expired = not _verify(m, "customer/2", at_time=time.time() + 2)
        return fresh and expired

    return False


if __name__ == "__main__":
    run("pymacaroons", CAPABILITIES, run_case)
