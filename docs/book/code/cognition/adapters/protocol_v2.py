"""v2 memory-store driver: identity-based authorization, adapter enforces no gate.

Wraps the v1 scenario machinery with the v2 authorization contract:

- A system that exposes real authentication implements ``authenticate(name,
  secret) -> token`` and ``issued_credentials() -> {name: secret}``. The
  *driver* obtains a token per principal and passes tokens — never raw
  principal names the adapter is free to interpret — into every operation.
- Before any case, the driver runs the negative-credential probe: a corrupted
  secret must be rejected by the system. A system that accepts garbage is not
  authenticating, and every authorization claim it makes is voided for the run.
- A system without an authentication surface cannot claim isolation,
  clearance, or purpose: those capabilities are stripped before the replay, so
  the cases are declined, never credited to adapter routing (issue #1).

What this catches: honest routing adapters and unauthenticated systems. What
it cannot catch: an adapter that deliberately fabricates an authentication
surface — that is handled by in-repo adapter review, with the published
``authorization_mechanism`` attestation making the claim explicit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from protocol import (  # noqa: E402
    MemorySystem,
    _run_case,
    supported,
)

AUTHORIZATION_CAPABILITIES = frozenset({"isolation", "clearance", "purpose"})
PRINCIPALS = ("operator", "analyst", "outsider", "advertiser")


class AuthenticatedMemorySystem(MemorySystem):
    """A v2 system whose principals are authenticated, not asserted.

    ``issued_credentials`` returns the secrets the *system* issued;
    ``authenticate`` exchanges one for an opaque principal token. Every
    memory operation then receives the token where v1 passed a name.
    """

    def issued_credentials(self) -> dict[str, str]:
        raise NotImplementedError

    def authenticate(self, name: str, secret: str) -> str | None:
        raise NotImplementedError


class _TokenView:
    """Presents the v1 MemorySystem surface with principals mapped to tokens.

    The scenario code addresses principals by name; this view swaps each name
    for the system-issued token before the call reaches the system, so the
    system's own authorization — not the adapter's interpretation of a name —
    decides every outcome.
    """

    def __init__(self, system: AuthenticatedMemorySystem, tokens: dict[str, str]) -> None:
        self._system = system
        self._tokens = tokens

    def __getattr__(self, name: str):
        return getattr(self._system, name)

    def _token(self, principal: str) -> str:
        return self._tokens.get(principal, f"unauthenticated:{principal}")

    def remember(self, memory_id, text, principal, **kwargs):
        return self._system.remember(memory_id, text, self._token(principal), **kwargs)

    def recall(self, query, principal, as_of=None):
        return self._system.recall(query, self._token(principal), as_of)

    def forget(self, memory_id, principal):
        return self._system.forget(memory_id, self._token(principal))

    def improve(self, memory_id, replacement_id, text, principal, *args, **kwargs):
        return self._system.improve(
            memory_id, replacement_id, text, self._token(principal), *args, **kwargs
        )


def prepare(system: MemorySystem):
    """Resolve the v2 authorization posture of one system.

    Returns ``(view, capabilities, mechanism, check)``: the (possibly
    token-mapped) system view to replay through, the effective capability set
    after stripping unauthenticated authorization claims, the attestation
    string, and the probe verdict.
    """

    mechanism = getattr(system, "authorization_mechanism", "none")
    is_authenticated = isinstance(system, AuthenticatedMemorySystem) or (
        hasattr(system, "authenticate") and hasattr(system, "issued_credentials")
    )
    if not is_authenticated:
        stripped = system.capabilities - AUTHORIZATION_CAPABILITIES
        check = (
            "not-applicable"
            if not (system.capabilities & AUTHORIZATION_CAPABILITIES)
            else "stripped-unauthenticated"
        )
        return system, stripped, "none", check

    secrets = system.issued_credentials()
    operator_secret = secrets.get("operator", "")
    forged = system.authenticate(
        "operator", operator_secret[:-1] + "x" if operator_secret else "forged"
    )
    if forged is not None:
        # Accepts a corrupted credential: not authenticating. Void every
        # authorization claim for the run.
        return (
            system,
            system.capabilities - AUTHORIZATION_CAPABILITIES,
            mechanism,
            "failed-negative-probe",
        )
    tokens = {}
    for principal in PRINCIPALS:
        token = system.authenticate(principal, secrets.get(principal, ""))
        if token is not None:
            tokens[principal] = token
    return _TokenView(system, tokens), system.capabilities, mechanism, "passed"


def run_v2(system: MemorySystem, stdin=None, stdout=None) -> None:
    """v2 adapter entry point: request on stdin, payload with attestation out."""

    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    request = json.loads(stdin.read())
    view, capabilities, mechanism, check = prepare(system)

    class _Scoped:
        """The view constrained to the effective v2 capability set."""

        def __init__(self) -> None:
            self.capabilities = capabilities

        def __getattr__(self, name: str):
            return getattr(view, name)

    scoped = _Scoped()
    temporal = "temporal" in capabilities
    rows = [_run_case(scoped, case, temporal) for case in request["cases"]]
    payload = {
        "adapter_version": f"{system.name}-{system.version}",
        "interface": "direct-api",
        "authorization_mechanism": str(mechanism)[:128],
        "authorization_check": check,
        "cases": rows,
    }
    stdout.write(json.dumps(payload) + "\n")
    stdout.flush()
