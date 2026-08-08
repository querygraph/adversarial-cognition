"""Comparative catalog execution for CATALOG-PROVENANCE-v1.

The reference catalog runs in-process. Each real catalog runs only when its
adapter command is explicitly configured through
``CATALOG_PROVENANCE_<CATALOG>_CMD``; the command receives the case corpus as
JSON on stdin and returns, per case, whether the capability is supported and
whether the outcome was correct. Unconfigured catalogs are reported
``unavailable``; a failing adapter is reported ``error`` — never converted into
a pass or a fail, never silently substituted.
"""

from __future__ import annotations

import json
import shlex
import subprocess

from .cases import CAPABILITIES, Case, cases, run_case
from .report import hard_gates, summarize

ADAPTER_PROTOCOL = "catalog-provenance-adapter-v1"
DEFAULT_TIMEOUT_SECONDS = 900
MAX_ERROR_CHARS = 256

EXTERNAL_CATALOGS = (
    ("lakecat", "CATALOG_PROVENANCE_LAKECAT_CMD"),
    ("polaris", "CATALOG_PROVENANCE_POLARIS_CMD"),
    ("gravitino", "CATALOG_PROVENANCE_GRAVITINO_CMD"),
    ("nessie", "CATALOG_PROVENANCE_NESSIE_CMD"),
)


def _case_row(case: Case, supported: bool, correct: bool) -> dict:
    return {
        "case_id": case.case_id,
        "capability": case.capability,
        "gate": case.gate,
        "supported": supported,
        "correct": correct,
    }


def _finish(catalog: str, adapter_version: str, capabilities: list[str],
            rows: list[dict]) -> dict:
    gates = hard_gates(rows)
    return {
        "catalog": catalog,
        "adapter_version": adapter_version,
        "status": "executed",
        "capabilities": sorted(capabilities),
        "hard_gates": gates,
        "summary": summarize(rows),
        "cases": rows,
    }


def run_reference(suite: tuple[Case, ...]) -> dict:
    """The reference catalog claims every capability and must pass every case."""

    rows = [_case_row(case, True, run_case(case)) for case in suite]
    return _finish("reference", "catalog-provenance-v1", list(CAPABILITIES), rows)


def _request(suite: tuple[Case, ...]) -> str:
    return json.dumps({
        "protocol": ADAPTER_PROTOCOL,
        "cases": [
            {"case_id": c.case_id, "capability": c.capability,
             "category": c.category, "gate": c.gate, "description": c.description}
            for c in suite
        ],
    }, sort_keys=True)


def _parse(payload: str, suite: tuple[Case, ...]) -> tuple[str, list[str], list[dict]]:
    parsed = json.loads(payload)
    version = str(parsed.get("adapter_version", ADAPTER_PROTOCOL))[:64]
    capabilities = [str(c) for c in parsed.get("capabilities", []) if c in CAPABILITIES]
    by_id = {row["case_id"]: row for row in parsed["cases"]}
    if set(by_id) != {c.case_id for c in suite}:
        raise ValueError("adapter did not report every case exactly once")
    rows = []
    for case in suite:
        row = by_id[case.case_id]
        supported = bool(row.get("supported", False))
        # A catalog cannot mark a case supported unless it also claimed the
        # capability that case exercises — no faking a boundary.
        supported = supported and case.capability in capabilities
        rows.append(_case_row(case, supported, supported and bool(row.get("correct", False))))
    return version, capabilities, rows


def execute_external(catalog: str, command_variable: str, suite: tuple[Case, ...],
                     environ: dict) -> dict:
    command = environ.get(command_variable, "").strip()
    if not command:
        return {"catalog": catalog, "status": "unavailable",
                "missing_configuration": [command_variable]}
    timeout = int(environ.get("CATALOG_PROVENANCE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    try:
        completed = subprocess.run(
            shlex.split(command), input=_request(suite), capture_output=True,
            text=True, timeout=timeout, check=True)
        version, capabilities, rows = _parse(completed.stdout, suite)
    except subprocess.CalledProcessError as error:
        # Surface the adapter's own reason (e.g. a preflight failure) rather
        # than the opaque exit-status message.
        reason = (error.stderr or "").strip().splitlines()
        detail = reason[-1] if reason else str(error)
        return {"catalog": catalog, "status": "error", "error": detail[:MAX_ERROR_CHARS]}
    except Exception as error:  # noqa: BLE001 - adapter failures are reportable
        return {"catalog": catalog, "status": "error", "error": str(error)[:MAX_ERROR_CHARS]}
    return _finish(catalog, version, capabilities, rows)


def execute_catalogs(selected: tuple[str, ...], suite: tuple[Case, ...],
                     environ: dict) -> list[dict]:
    known = ("reference",) + tuple(name for name, _ in EXTERNAL_CATALOGS)
    unknown = set(selected) - set(known)
    if unknown:
        raise ValueError(f"unknown catalogs: {sorted(unknown)}")
    results = []
    if "reference" in selected:
        results.append(run_reference(suite))
    for name, variable in EXTERNAL_CATALOGS:
        if name in selected:
            results.append(execute_external(name, variable, suite, environ))
    return results
