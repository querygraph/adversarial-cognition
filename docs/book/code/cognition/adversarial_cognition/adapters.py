"""Comparative system adapters for MARCIANA-ADVERSARIAL-v1.

Every configured system is enumerated explicitly. A system that is not
configured reports ``unavailable`` with its missing configuration; a failing
adapter reports ``error``. No adapter is ever silently substituted for
another.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import time
from dataclasses import dataclass

from .cases import Case, run_case

ADAPTER_PROTOCOL = "marciana-adversarial-adapter-v1"
EXTERNAL_TIMEOUT_SECONDS = 600
MAX_ERROR_CHARS = 256

EXTERNAL_SYSTEMS = (
    ("mem0", "MARCIANA_ADVERSARIAL_MEM0_CMD"),
    ("letta", "MARCIANA_ADVERSARIAL_LETTA_CMD"),
    # Optional second Letta entry driving its memory store directly rather than
    # through the agent loop, so the cost of the loop can be read as the delta
    # between the two rows. Same adapter, LETTA_ADAPTER_MODE=direct-memory.
    ("letta-direct", "MARCIANA_ADVERSARIAL_LETTA_DIRECT_CMD"),
    ("cognee", "MARCIANA_ADVERSARIAL_COGNEE_CMD"),
    ("cognee-rs", "MARCIANA_ADVERSARIAL_COGNEE_RS_CMD"),
    ("graphiti", "MARCIANA_ADVERSARIAL_GRAPHITI_CMD"),
    ("akka-fluree", "MARCIANA_ADVERSARIAL_AKKA_FLUREE_CMD"),
)


@dataclass(frozen=True)
class CaseOutcome:
    case_id: str
    category: str
    correct: bool
    allowed: bool
    returned_ids: tuple[str, ...]
    receipt: str
    latency_us: float
    supported: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "correct": self.correct,
            "allowed": self.allowed,
            "returned_ids": list(self.returned_ids),
            "receipt": self.receipt,
            "latency_us": round(self.latency_us, 3),
            "supported": self.supported,
        }


@dataclass(frozen=True)
class SystemReport:
    system: str
    adapter_version: str
    status: str
    missing_configuration: tuple[str, ...] = ()
    error: str = ""
    interface: str = "direct-api"
    outcomes: tuple[CaseOutcome, ...] = ()

    def as_dict(self) -> dict[str, object]:
        report: dict[str, object] = {
            "system": self.system,
            "adapter_version": self.adapter_version,
            "status": self.status,
        }
        if self.missing_configuration:
            report["missing_configuration"] = list(self.missing_configuration)
        if self.error:
            report["error"] = self.error
        if self.status == "executed":
            report["interface"] = self.interface
            report["cases"] = [outcome.as_dict() for outcome in self.outcomes]
            report["unsupported_cases"] = sum(
                not outcome.supported for outcome in self.outcomes
            )
        return report


def execute_marciana(suite: tuple[Case, ...], repeats: int) -> SystemReport:
    """Run the deterministic reference path, timing each full case run."""

    outcomes = []
    for case in suite:
        started = time.perf_counter_ns()
        for _ in range(repeats):
            correct, decision = run_case(case)
        elapsed_us = (time.perf_counter_ns() - started) / 1_000 / repeats
        outcomes.append(
            CaseOutcome(
                case.case_id,
                case.category,
                correct,
                decision.allowed,
                decision.ids,
                decision.receipt,
                elapsed_us,
            )
        )
    return SystemReport("marciana", ADAPTER_PROTOCOL, "executed",
                        interface="direct-api", outcomes=tuple(outcomes))


def _external_request(suite: tuple[Case, ...], repeats: int) -> str:
    return json.dumps(
        {
            "protocol": ADAPTER_PROTOCOL,
            "repeats": repeats,
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
        },
        sort_keys=True,
    )


def _parse_external_outcomes(
    payload: str, suite: tuple[Case, ...]
) -> tuple[str, str, tuple[CaseOutcome, ...]]:
    """Parse an external adapter's payload into a version, interface, and outcomes.

    An adapter may honestly declare a case ``"supported": false`` instead of
    faking a result for a feature its system does not claim; unsupported
    cases are reported separately, never counted as passes. The optional
    ``interface`` field records how the adapter reached the system's memory
    (``direct-api`` or ``agent-loop``); it is metadata, never a score.
    """

    parsed = json.loads(payload)
    version = str(parsed.get("adapter_version", ADAPTER_PROTOCOL))[:64]
    interface = str(parsed.get("interface", "direct-api"))[:32]
    rows = parsed["cases"]
    by_id = {row["case_id"]: row for row in rows}
    if set(by_id) != {case.case_id for case in suite}:
        raise ValueError("external adapter did not report every case exactly once")
    return version, interface, tuple(
        CaseOutcome(
            case.case_id,
            case.category,
            bool(by_id[case.case_id]["correct"]),
            bool(by_id[case.case_id]["allowed"]),
            tuple(str(item) for item in by_id[case.case_id].get("returned_ids", ())),
            str(by_id[case.case_id].get("receipt", "")),
            float(by_id[case.case_id].get("latency_us", 0.0)),
            bool(by_id[case.case_id].get("supported", True)),
        )
        for case in suite
    )


def execute_external(
    system: str,
    command_variable: str,
    suite: tuple[Case, ...],
    repeats: int,
    environ: dict[str, str],
) -> SystemReport:
    """Run one explicitly configured external adapter command.

    The command receives the case corpus as JSON on stdin and must print a
    ``{"cases": [...]}`` payload with one outcome per case. Endpoint or API
    credentials belong to the adapter command's own environment.
    """

    command = environ.get(command_variable, "").strip()
    if not command:
        return SystemReport(
            system, ADAPTER_PROTOCOL, "unavailable", missing_configuration=(command_variable,)
        )
    timeout = int(environ.get("MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS", EXTERNAL_TIMEOUT_SECONDS))
    try:
        completed = subprocess.run(
            shlex.split(command),
            input=_external_request(suite, repeats),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        version, interface, outcomes = _parse_external_outcomes(completed.stdout, suite)
    except Exception as error:  # noqa: BLE001 - adapter failures become reportable errors
        return SystemReport(
            system, ADAPTER_PROTOCOL, "error", error=str(error)[:MAX_ERROR_CHARS]
        )
    return SystemReport(system, version, "executed", interface=interface, outcomes=outcomes)


def execute_systems(
    selected: tuple[str, ...],
    suite: tuple[Case, ...],
    repeats: int,
    environ: dict[str, str],
) -> tuple[SystemReport, ...]:
    """Execute every selected system, in declaration order, marciana first."""

    known = ("marciana",) + tuple(system for system, _ in EXTERNAL_SYSTEMS)
    unknown = set(selected) - set(known)
    if unknown:
        raise ValueError(f"unknown benchmark systems: {sorted(unknown)}")
    reports = []
    if "marciana" in selected:
        reports.append(execute_marciana(suite, repeats))
    for system, command_variable in EXTERNAL_SYSTEMS:
        if system in selected:
            reports.append(execute_external(system, command_variable, suite, repeats, environ))
    return tuple(reports)
