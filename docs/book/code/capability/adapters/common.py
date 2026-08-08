"""Shared stdio harness for CAPABILITY-ADVERSARIAL-v1 competitor adapters.

An adapter module defines two things and calls :func:`run`:

- ``CAPABILITIES`` — the list of capability names the system genuinely enforces;
- ``run_case(case_id) -> bool`` — the correct-outcome check for a claimed case,
  implemented with the system's *real* library.

The harness reads the case corpus on stdin and, for every case, marks it
``supported`` only when its capability is one the adapter claims — a system is
never scored on a capability it does not declare, and ``run_case`` is only
invoked for claimed cases. The result is printed as the adapter-protocol JSON.
"""

from __future__ import annotations

import json
import sys
from typing import Callable


def run(adapter_version: str, capabilities: list[str],
        run_case: Callable[[str], bool]) -> None:
    request = json.load(sys.stdin)
    claimed = set(capabilities)
    rows = []
    for case in request["cases"]:
        case_id = case["case_id"]
        supported = case.get("capability") in claimed
        correct = False
        if supported:
            try:
                correct = bool(run_case(case_id))
            except Exception as error:  # noqa: BLE001 - a probe failure is a finding
                sys.stderr.write(f"{case_id}: {error}\n")
                correct = False
        rows.append({"case_id": case_id, "supported": supported, "correct": correct})
    json.dump({
        "adapter_version": adapter_version,
        "capabilities": sorted(claimed),
        "cases": rows,
    }, sys.stdout)
