"""OPA / Rego adapter — a policy engine, in the same band as Cedar.

Open Policy Agent evaluates a default-deny Rego policy for a
(principal, action, resource) input. Like any decision engine it mints no
capability token, so it claims only the columns a decision covers:
resource-instance-binding, deny-by-default-tool, confused-deputy-resistance.
Everything token-shaped — mint, attenuation, revocation, lease, reveal — is
declared unsupported.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__) + "/..")
from common import run  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OPA = os.path.join(HERE, "bin", "opa")
POLICY = os.path.join(HERE, "policy.rego")

CAPABILITIES = ["resource-instance-binding", "deny-by-default-tool", "confused-deputy-resistance"]


def _allow(principal: str, action: str, resource: str) -> bool:
    inp = json.dumps({"principal": principal, "action": action, "resource": resource})
    out = subprocess.run(
        [OPA, "eval", "-d", POLICY, "-I", "--format", "raw", "data.capability.allow"],
        input=inp, capture_output=True, text=True, check=True)
    return out.stdout.strip() == "true"


def run_case(case_id: str) -> bool:
    if case_id == "resource-instance-bound":
        return _allow("agent:operator", "read", "customer/2")
    if case_id == "cross-resource-rejected":
        return not _allow("agent:operator", "read", "customer/1")
    if case_id == "ambient-tool-call-denied":
        return not _allow("agent:analyst", "execute", "tool:x")
    if case_id == "confused-deputy-rejected":
        return (_allow("agent:operator", "search", "tool:x")
                and not _allow("agent:operator", "delete", "tool:x"))
    return False


if __name__ == "__main__":
    run("opa-1.19", CAPABILITIES, run_case)
