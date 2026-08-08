"""SpiceDB adapter — relationship-based access control (ReBAC).

SpiceDB (AuthZed's Zanzibar implementation) answers a permission check against a
schema of relations and permissions plus a set of relationships. It is the other
ReBAC engine in the policy-decision band: it mints no capability token, and lands
where Cedar, OPA, and OpenFGA do — reached through relationships and derived
permissions. It claims only the decision columns:

- `resource-instance-binding` — a relationship names one resource object;
- `deny-by-default-tool` — no relationship, no permission (default deny);
- `confused-deputy-resistance` — `search` and `delete` are distinct permissions,
  so authority for one never grants the other.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__) + "/..")
from common import run  # noqa: E402

BASE = os.environ.get("SPICEDB_URL", "http://localhost:8446").rstrip("/")
KEY = os.environ.get("SPICEDB_KEY", "capadv")
CAPABILITIES = ["resource-instance-binding", "deny-by-default-tool", "confused-deputy-resistance"]

SCHEMA = (
    "definition user {}\n"
    "definition document {\n  relation reader: user\n  permission read = reader\n}\n"
    "definition tool {\n  relation searcher: user\n  relation deleter: user\n"
    "  permission search = searcher\n  permission delete = deleter\n}"
)


def _post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "authorization": f"Bearer {KEY}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _rel(obj_type: str, obj_id: str, relation: str, user_id: str) -> dict:
    return {"operation": "OPERATION_TOUCH", "relationship": {
        "resource": {"objectType": obj_type, "objectId": obj_id},
        "relation": relation,
        "subject": {"object": {"objectType": "user", "objectId": user_id}}}}


def _setup() -> None:
    _post("/v1/schema/write", {"schema": SCHEMA})
    _post("/v1/relationships/write", {"updates": [
        _rel("document", "customer2", "reader", "operator"),
        _rel("tool", "x", "searcher", "operator"),
    ]})


_setup()


def _check(obj_type: str, obj_id: str, permission: str, user_id: str) -> bool:
    out = _post("/v1/permissions/check", {
        "resource": {"objectType": obj_type, "objectId": obj_id},
        "permission": permission,
        "subject": {"object": {"objectType": "user", "objectId": user_id}},
        # Read at the freshest revision so a check sees the relationships just
        # written — otherwise SpiceDB may answer from an older snapshot.
        "consistency": {"fullyConsistent": True}})
    return out.get("permissionship") == "PERMISSIONSHIP_HAS_PERMISSION"


def run_case(case_id: str) -> bool:
    if case_id == "resource-instance-bound":
        return _check("document", "customer2", "read", "operator")
    if case_id == "cross-resource-rejected":
        return not _check("document", "customer1", "read", "operator")
    if case_id == "ambient-tool-call-denied":
        return not _check("tool", "x", "search", "analyst")
    if case_id == "confused-deputy-rejected":
        return (_check("tool", "x", "search", "operator")
                and not _check("tool", "x", "delete", "operator"))
    return False


if __name__ == "__main__":
    run("spicedb", CAPABILITIES, run_case)
