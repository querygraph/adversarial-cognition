"""Hard gates, metrics, and report assembly for MARCIANA-ADVERSARIAL-v1.

Safety failures are counted in named hard gates that must all be zero; they
are never averaged into a quality score. Reports carry bounded IDs, digests,
counts, and timings only — never memory plaintext.
"""

from __future__ import annotations

import json

from .adapters import CaseOutcome, SystemReport
from .backend import digest
from .cases import CORPUS_VERSION, Case
from .metrics import percentile
from .tracks import group_by_track, track_for_interface

BENCHMARK = "MARCIANA-ADVERSARIAL-v1"
BENCHMARK_V2 = "MARCIANA-ADVERSARIAL-v2"
MAX_REPORT_TEXT = 256

CATEGORY_GATES = {
    "authorization": "unauthorized_disclosure",
    "provenance": "invalid_provenance_accepted",
    "mutation": "stale_proposal_committed",
    "replay": "replayed_mutation_accepted",
    "recovery": "duplicate_durable_mutation",
    "forget": "residual_recall_after_forget",
    "reproducibility": "non_deterministic_receipts",
    "robustness": "adversarial_input_mishandled",
}
CASE_GATES = {"isolation-tenant": "cross_scope_leakage"}
GATE_NAMES = tuple(dict.fromkeys((*CASE_GATES.values(), *CATEGORY_GATES.values())))


def corpus_manifest(suite: tuple[Case, ...]) -> dict[str, object]:
    return {
        "benchmark": BENCHMARK,
        "corpus_version": CORPUS_VERSION,
        "cases": [
            {
                "case_id": case.case_id,
                "category": case.category,
                "description": case.description,
                "expected_allowed": case.expected_allowed,
                "expected_ids": list(case.expected_ids),
                "must_abstain": case.must_abstain,
                "forbidden_ids": list(case.forbidden_ids),
            }
            for case in suite
        ],
    }


def corpus_digest(manifest: dict[str, object]) -> str:
    return digest(json.dumps(manifest, sort_keys=True))


def hard_gates(
    outcomes: tuple[CaseOutcome, ...], receipt_mismatches: int
) -> dict[str, int]:
    gates = {name: 0 for name in GATE_NAMES}
    for outcome in outcomes:
        gate = CASE_GATES.get(outcome.case_id, CATEGORY_GATES.get(outcome.category))
        if gate and not outcome.correct:
            gates[gate] += 1
    gates["non_deterministic_receipts"] += receipt_mismatches
    return gates


def receipt_mismatches(
    first: tuple[CaseOutcome, ...], second: tuple[CaseOutcome, ...]
) -> int:
    """Count cases whose receipt or result differs between two identical runs."""

    paired = zip(first, second, strict=True)
    return sum(
        1
        for one, two in paired
        if (one.receipt, one.returned_ids) != (two.receipt, two.returned_ids)
    )


def quality(outcomes: tuple[CaseOutcome, ...]) -> dict[str, object]:
    # Accuracy is computed over supported cases only; a declared-unsupported
    # case is reported separately and never counted as a pass or a failure.
    supported = tuple(o for o in outcomes if o.supported)
    by_category: dict[str, list[CaseOutcome]] = {}
    for outcome in supported:
        by_category.setdefault(outcome.category, []).append(outcome)
    abstentions = by_category.get("abstention", [])
    return {
        "accuracy": (sum(o.correct for o in supported) / len(supported)) if supported else 0.0,
        "unsupported_cases": len(outcomes) - len(supported),
        "category_accuracy": {
            category: sum(o.correct for o in rows) / len(rows)
            for category, rows in sorted(by_category.items())
        },
        "unsupported_answer_rate": (
            sum(bool(o.returned_ids) for o in abstentions) / len(abstentions)
            if abstentions
            else 0.0
        ),
    }


def performance(
    outcomes: tuple[CaseOutcome, ...],
    formation_us: float,
    restart_us: float,
) -> dict[str, float]:
    latencies = [outcome.latency_us for outcome in outcomes]
    return {
        "p50_latency_us": round(percentile(latencies, 50), 3),
        "p95_latency_us": round(percentile(latencies, 95), 3),
        "p99_latency_us": round(percentile(latencies, 99), 3),
        "formation_us": round(formation_us, 3),
        "restart_us": round(restart_us, 3),
    }


def overall_status(gates: dict[str, int], systems: tuple[SystemReport, ...]) -> str:
    marciana = next((report for report in systems if report.system == "marciana"), None)
    if any(gates.values()):
        return "fail"
    if marciana is None or marciana.status != "executed":
        return "incomplete"
    return "pass"


def assert_bounded(report: dict[str, object]) -> None:
    """Reject reports carrying plaintext-sized strings anywhere in the tree."""

    def walk(value: object) -> None:
        if isinstance(value, str):
            if len(value) > MAX_REPORT_TEXT or "\n" in value:
                raise ValueError("benchmark report contains an unbounded string")
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(key)
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(report)


def build_report(
    metadata: dict[str, str],
    manifest_digest: str,
    systems: tuple[SystemReport, ...],
    receipt_mismatch_count: int,
    formation_us: float,
    restart_us: float,
    corpora: dict[str, object],
    benchmark: str = BENCHMARK,
) -> dict[str, object]:
    marciana = next((report for report in systems if report.system == "marciana"), None)
    outcomes = marciana.outcomes if marciana and marciana.status == "executed" else ()
    gates = hard_gates(outcomes, receipt_mismatch_count)
    system_entries = {system.system: system.as_dict() for system in systems}
    report = {
        "benchmark": benchmark,
        "corpus_digest": manifest_digest,
        "status": overall_status(gates, systems),
        "metadata": metadata,
        "hard_gates": gates,
        "systems": system_entries,
        "cases": [outcome.as_dict() for outcome in outcomes],
        "quality": quality(outcomes) if outcomes else {},
        "performance": performance(outcomes, formation_us, restart_us) if outcomes else {},
        "public_corpora": corpora,
    }
    if benchmark == BENCHMARK_V2:
        # v2 promotes the interface to a first-class track: every executed
        # system is stamped with its track, and the report carries the
        # grouping so the renderer compares only within a track. The v1 path
        # emits none of these keys and stays byte-for-byte stable.
        for entry in system_entries.values():
            if entry.get("status") == "executed":
                entry["track"] = track_for_interface(
                    entry.get("interface", "direct-api")
                )
        report["tracks"] = group_by_track(system_entries)
    assert_bounded(report)
    return report
