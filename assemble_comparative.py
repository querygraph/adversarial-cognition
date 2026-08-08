"""Assemble a comparative report from saved per-adapter outputs.

The slow OSS adapters run once; their raw JSON outputs are captured under
outputs/<system>.json. This assembles those with a fresh in-process Marciana
reference run into the standard comparative report, without re-invoking the
adapters. Systems with no saved output are reported ``unavailable``; a saved
output that fails to parse is reported ``error``.
"""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

from adversarial_cognition.adapters import (
    EXTERNAL_SYSTEMS,
    SystemReport,
    _parse_external_outcomes,
    execute_marciana,
)
from adversarial_cognition.cases import cases
from adversarial_cognition.metadata import BenchmarkMetadata
from adversarial_cognition.report import (
    build_report,
    corpus_digest,
    corpus_manifest,
    receipt_mismatches,
)

OUTPUTS = Path("outputs")


def load_system(system: str, suite: tuple) -> SystemReport:
    path = OUTPUTS / f"{system}.json"
    if not path.exists():
        variable = dict(EXTERNAL_SYSTEMS)[system]
        return SystemReport(system, "adapter", "unavailable", missing_configuration=(variable,))
    try:
        version, interface, harness, outcomes = _parse_external_outcomes(
            path.read_text(), suite
        )
    except Exception as error:  # noqa: BLE001 - a bad capture is a reportable error
        return SystemReport(system, "adapter", "error", error=str(error)[:256])
    return SystemReport(
        system, version, "executed",
        interface=interface, outcomes=outcomes, harness=harness,
    )


def main() -> None:
    suite = cases()
    manifest = corpus_manifest(suite)
    marciana = execute_marciana(suite, 20)
    mismatches = receipt_mismatches(
        execute_marciana(suite, 1).outcomes, execute_marciana(suite, 1).outcomes
    )
    systems = (marciana,) + tuple(
        load_system(system, suite) for system, _ in EXTERNAL_SYSTEMS
    )
    metadata = BenchmarkMetadata(
        model="reference-smoke-v1",
        provider="local-ollama",
        embedding="nomic-embed-text",
        prompt="none",
        profile="adversarial-v1-comparative",
        hardware=platform.platform(),
        revision="working-tree",
    )
    report = build_report(
        metadata.as_dict(), corpus_digest(manifest), systems, mismatches,
        marciana.outcomes[0].latency_us if marciana.outcomes else 0.0, 0.0, {},
    )
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "reports/marciana-adversarial-v1-comparative.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    executed = [s.system for s in systems if s.status == "executed"]
    print(f"assembled {out}: status={report['status']}, executed={executed}")


if __name__ == "__main__":
    main()
