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

# v2 registry. The native-loop letta entry is retired as a ranked row (its
# payload cannot carry a harness attestation, which v2 requires for
# agent-loop); the agent-memory track runs backends under the shared harness.
EXTERNAL_SYSTEMS_V2 = (
    ("mem0", "MARCIANA_ADVERSARIAL_MEM0_CMD"),
    ("letta-direct", "MARCIANA_ADVERSARIAL_LETTA_DIRECT_CMD"),
    ("cognee", "MARCIANA_ADVERSARIAL_COGNEE_CMD"),
    ("cognee-rs", "MARCIANA_ADVERSARIAL_COGNEE_RS_CMD"),
    ("graphiti", "MARCIANA_ADVERSARIAL_GRAPHITI_CMD"),
    ("akka-fluree", "MARCIANA_ADVERSARIAL_AKKA_FLUREE_CMD"),
    ("marciana-agent", "MARCIANA_ADVERSARIAL_MARCIANA_AGENT_CMD"),
    ("memfs-agent", "MARCIANA_ADVERSARIAL_MEMFS_AGENT_CMD"),
    ("letta-agent", "MARCIANA_ADVERSARIAL_LETTA_AGENT_CMD"),
)


def external_systems(benchmark_version: int = 1) -> tuple[tuple[str, str], ...]:
    return EXTERNAL_SYSTEMS_V2 if benchmark_version >= 2 else EXTERNAL_SYSTEMS


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
    harness: dict | None = None

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
            if self.harness:
                report["harness"] = dict(self.harness)
        return report


def execute_marciana(
    suite: tuple[Case, ...], repeats: int, runner=run_case
) -> SystemReport:
    """Run the deterministic reference path, timing each full case run.

    ``runner`` selects the reference execution: the v1 ``run_case`` (default)
    or the v2 ``run_case_v2``, which replays through authenticated sessions.
    """

    outcomes = []
    for case in suite:
        started = time.perf_counter_ns()
        for _ in range(repeats):
            correct, decision = runner(case)
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


HARNESS_KEYS = (
    "model", "seed", "temperature", "num_ctx", "max_turns",
    "prompt_digest", "tool_contract",
)


def _parse_harness(parsed: dict, interface: str, benchmark_version: int) -> dict | None:
    """Validate the harness attestation an agent-loop payload must carry (v2).

    Under v2, ``agent-loop`` is only a valid interface when the shared harness
    itself stamped the payload with its configuration; a self-declared
    agent-loop adapter that did not run under the harness would land in the
    agent-memory track while violating its one-loop premise.
    """

    harness = parsed.get("harness")
    if benchmark_version < 2:
        return None
    if interface != "agent-loop":
        return None
    if not isinstance(harness, dict):
        raise ValueError("agent-loop declared without a harness attestation")
    missing = [key for key in HARNESS_KEYS if key not in harness]
    if missing:
        raise ValueError(f"harness attestation missing keys: {missing}")
    bounded: dict[str, object] = {}
    for key in HARNESS_KEYS:
        value = harness[key]
        bounded[key] = str(value)[:128] if isinstance(value, str) else value
    return bounded


def _parse_external_outcomes(
    payload: str, suite: tuple[Case, ...], benchmark_version: int = 1
) -> tuple[str, str, dict | None, tuple[CaseOutcome, ...]]:
    """Parse an external adapter's payload into version, interface, harness, outcomes.

    An adapter may honestly declare a case ``"supported": false`` instead of
    faking a result for a feature its system does not claim; unsupported
    cases are reported separately, never counted as passes. The ``interface``
    field records how the adapter reached the system's memory (``direct-api``
    or ``agent-loop``). Under v1 it is optional metadata defaulting to
    ``direct-api``; under v2 it is required, and ``agent-loop`` must carry the
    harness attestation block the shared harness stamps.
    """

    parsed = json.loads(payload)
    version = str(parsed.get("adapter_version", ADAPTER_PROTOCOL))[:64]
    if benchmark_version >= 2 and "interface" not in parsed:
        raise ValueError("v2 adapter payload must declare its interface")
    interface = str(parsed.get("interface", "direct-api"))[:32]
    harness = _parse_harness(parsed, interface, benchmark_version)
    rows = parsed["cases"]
    by_id = {row["case_id"]: row for row in rows}
    if set(by_id) != {case.case_id for case in suite}:
        raise ValueError("external adapter did not report every case exactly once")
    return version, interface, harness, tuple(
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
    benchmark_version: int = 1,
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
        version, interface, harness, outcomes = _parse_external_outcomes(
            completed.stdout, suite, benchmark_version
        )
    except Exception as error:  # noqa: BLE001 - adapter failures become reportable errors
        message = str(error)
        # A failing adapter's own last words are more legible than the bare
        # exit status; surface the stderr tail (bounded) when present.
        stderr = getattr(error, "stderr", "") or ""
        if stderr.strip():
            message = stderr.strip().replace("\n", " ")
        return SystemReport(
            system, ADAPTER_PROTOCOL, "error", error=message[:MAX_ERROR_CHARS]
        )
    return SystemReport(
        system, version, "executed",
        interface=interface, outcomes=outcomes, harness=harness,
    )


def execute_systems(
    selected: tuple[str, ...],
    suite: tuple[Case, ...],
    repeats: int,
    environ: dict[str, str],
    benchmark_version: int = 1,
    runner=run_case,
) -> tuple[SystemReport, ...]:
    """Execute every selected system, in declaration order, marciana first."""

    registry = external_systems(benchmark_version)
    known = ("marciana",) + tuple(system for system, _ in registry)
    unknown = set(selected) - set(known)
    if unknown:
        raise ValueError(f"unknown benchmark systems: {sorted(unknown)}")
    reports = []
    if "marciana" in selected:
        reports.append(execute_marciana(suite, repeats, runner))
    for system, command_variable in registry:
        if system in selected:
            reports.append(
                execute_external(
                    system, command_variable, suite, repeats, environ,
                    benchmark_version,
                )
            )
    return tuple(reports)
