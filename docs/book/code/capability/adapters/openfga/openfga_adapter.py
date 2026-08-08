"""OpenFGA adapter — relationship-based access control (ReBAC).

OpenFGA (the CNCF Zanzibar-style engine) answers `check(user, relation, object)`
against a set of relationship tuples and an authorization model. Like any
decision engine it mints no capability token, so it claims only the columns a
ReBAC decision covers — and it lands in the same band as Cedar and OPA, reached
by a different mechanism (tuples, not policy rules):

- `resource-instance-binding` — a tuple names one object instance; another is
  denied for lack of a tuple;
- `deny-by-default-tool` — no tuple, no access (default deny);
- `confused-deputy-resistance` — relations are distinct, so a `searcher` tuple
  never grants `deleter`.

Everything token-shaped — mint, attenuation, revocation, lease, reveal — has no
ReBAC analog and is declared unsupported.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__) + "/..")
from common import run  # noqa: E402

BASE = os.environ.get("OPENFGA_URL", "http://localhost:8085").rstrip("/")
CAPABILITIES = ["resource-instance-binding", "deny-by-default-tool", "confused-deputy-resistance"]

MODEL = {
    "schema_version": "1.1",
    "type_definitions": [
        {"type": "user"},
        {"type": "document",
         "relations": {"reader": {"this": {}}, "writer": {"this": {}}},
         "metadata": {"relations": {
             "reader": {"directly_related_user_types": [{"type": "user"}]},
             "writer": {"directly_related_user_types": [{"type": "user"}]}}}},
        {"type": "tool",
         "relations": {"searcher": {"this": {}}, "deleter": {"this": {}}},
         "metadata": {"relations": {
             "searcher": {"directly_related_user_types": [{"type": "user"}]},
             "deleter": {"directly_related_user_types": [{"type": "user"}]}}}},
    ],
}

TUPLES = [
    {"user": "user:operator", "relation": "reader", "object": "document:customer2"},
    {"user": "user:operator", "relation": "searcher", "object": "tool:x"},
]


def _post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _setup() -> tuple[str, str]:
    store = _post("/stores", {"name": "cap-adv"})["id"]
    model_id = _post(f"/stores/{store}/authorization-models", MODEL)["authorization_model_id"]
    _post(f"/stores/{store}/write",
          {"writes": {"tuple_keys": TUPLES}, "authorization_model_id": model_id})
    return store, model_id


_STORE, _MODEL_ID = _setup()


def _check(user: str, relation: str, obj: str) -> bool:
    out = _post(f"/stores/{_STORE}/check", {
        "tuple_key": {"user": user, "relation": relation, "object": obj},
        "authorization_model_id": _MODEL_ID})
    return bool(out.get("allowed", False))


def run_case(case_id: str) -> bool:
    if case_id == "resource-instance-bound":
        return _check("user:operator", "reader", "document:customer2")
    if case_id == "cross-resource-rejected":
        return not _check("user:operator", "reader", "document:customer1")
    if case_id == "ambient-tool-call-denied":
        return not _check("user:analyst", "searcher", "tool:x")
    if case_id == "confused-deputy-rejected":
        return (_check("user:operator", "searcher", "tool:x")
                and not _check("user:operator", "deleter", "tool:x"))
    return False


if __name__ == "__main__":
    run("openfga", CAPABILITIES, run_case)
