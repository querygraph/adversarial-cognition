"""Hard gates, metrics, and report assembly for CAPABILITY-ADVERSARIAL-v1.

Safety failures are counted in named hard gates that must all be zero; they are
never averaged into a quality score. A system is scored only on the capabilities
it declares — a case whose capability the system does not claim is
``unsupported``, never a pass or a failure. Reports carry bounded IDs, digests,
and counts only.
"""

from __future__ import annotations

import json

from .backend import digest
from .cases import CORPUS_VERSION, GATES, Case

BENCHMARK = "CAPABILITY-ADVERSARIAL-v1"
MAX_REPORT_TEXT = 256


def corpus_manifest(suite: tuple[Case, ...]) -> dict:
    return {
        "benchmark": BENCHMARK,
        "corpus_version": CORPUS_VERSION,
        "cases": [
            {
                "case_id": c.case_id,
                "category": c.category,
                "capability": c.capability,
                "description": c.description,
                "gate": c.gate,
            }
            for c in suite
        ],
    }


def corpus_digest(manifest: dict) -> str:
    return digest("manifest", json.dumps(manifest, sort_keys=True))


def hard_gates(case_outcomes: list[dict]) -> dict[str, int]:
    """Count gate violations. A gate trips only on a *supported* case that a
    system got wrong — an honestly-declared unsupported case never trips it."""

    gates = {name: 0 for name in GATES}
    for outcome in case_outcomes:
        gate = outcome.get("gate")
        if gate and outcome.get("supported", True) and not outcome.get("correct", False):
            gates[gate] += 1
    return gates


def summarize(case_outcomes: list[dict]) -> dict:
    supported = [c for c in case_outcomes if c.get("supported", True)]
    passed = sum(1 for c in supported if c.get("correct"))
    return {
        "supported": len(supported),
        "correct": passed,
        "unsupported": len(case_outcomes) - len(supported),
        "accuracy": (passed / len(supported)) if supported else 0.0,
    }


def system_status(status: str, gates: dict[str, int]) -> str:
    if status != "executed":
        return status
    return "fail" if any(gates.values()) else "pass"


def assert_bounded(report: dict) -> None:
    """Reject any plaintext-sized string anywhere in the report tree."""

    def walk(value: object) -> None:
        if isinstance(value, str):
            if len(value) > MAX_REPORT_TEXT or "\n" in value:
                raise ValueError("capability-adversarial report contains an unbounded string")
        elif isinstance(value, dict):
            for k, v in value.items():
                walk(k)
                walk(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                walk(v)

    walk(report)


def build_report(metadata: dict, manifest_digest: str, systems: list[dict]) -> dict:
    reference = next((s for s in systems if s["system"] == "reference"), None)
    overall = "pass"
    if reference is None or reference.get("status") != "executed":
        overall = "incomplete"
    elif any(reference.get("hard_gates", {}).values()):
        overall = "fail"

    report = {
        "benchmark": BENCHMARK,
        "corpus_digest": manifest_digest,
        "status": overall,
        "metadata": metadata,
        "systems": systems,
    }
    assert_bounded(report)
    return report
