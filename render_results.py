"""Render a comparative benchmark report into a Markdown results document.

Reads the JSON emitted by run_comparative.sh and writes docs/RESULTS.md: a
per-system status line, the hard-gate ledger, and a case-by-system matrix
using ✓ (correct), ✗ (failed, a finding about that system), and · (the
system honestly declared the case unsupported).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CORRECT, FAILED, UNSUPPORTED = "✓", "✗", "·"


def cell(case: dict) -> str:
    if not case.get("supported", True):
        return UNSUPPORTED
    return CORRECT if case["correct"] else FAILED


def render(report: dict) -> str:
    systems = report["systems"]
    order = ["marciana", "mem0", "zep", "letta", "cognee", "graphiti", "akka-fluree"]
    present = [name for name in order if name in systems] + [
        name for name in systems if name not in order
    ]
    executed = [name for name in present if systems[name]["status"] == "executed"]

    lines = [
        "# MARCIANA-ADVERSARIAL-v1 comparative results",
        "",
        f"**Benchmark:** {report['benchmark']}  ",
        f"**Corpus digest:** `{report['corpus_digest']}`  ",
        f"**Overall status:** {report['status']}  ",
        f"**Profile:** {report['metadata'].get('profile', '')} on "
        f"{report['metadata'].get('provider', '')}",
        "",
        "Comparative systems run through their own OSS stacks with local models "
        "(Ollama) and local infrastructure. A cell is ✓ when the system produced "
        "the correct outcome, ✗ when it did not (a finding about that system), and "
        "· when the system honestly declared the case unsupported — never scored "
        "as a pass or a failure.",
        "",
        "## Systems",
        "",
        "| System | Status | Adapter | Accuracy (supported) | Unsupported |",
        "|--------|--------|---------|---------------------|-------------|",
    ]
    for name in present:
        entry = systems[name]
        status = entry["status"]
        if status == "executed":
            cases = entry["cases"]
            supported = [c for c in cases if c.get("supported", True)]
            acc = sum(c["correct"] for c in supported) / len(supported) if supported else 0.0
            unsupported = sum(not c.get("supported", True) for c in cases)
            lines.append(
                f"| {name} | executed | `{entry['adapter_version']}` | "
                f"{acc:.0%} ({sum(c['correct'] for c in supported)}/{len(supported)}) | "
                f"{unsupported} |"
            )
        else:
            missing = ", ".join(entry.get("missing_configuration", ())) or entry.get("error", "")
            lines.append(f"| {name} | {status} | — | — | {missing} |")

    lines += ["", "## Hard gates (Marciana reference)", ""]
    lines.append("| Gate | Count |")
    lines.append("|------|-------|")
    for gate, count in sorted(report["hard_gates"].items()):
        lines.append(f"| `{gate}` | {count} |")

    if executed:
        lines += ["", "## Case matrix", "",
                  "| Case | Category | " + " | ".join(executed) + " |",
                  "|------|----------|" + "|".join(["---"] * len(executed)) + "|"]
        case_ids = [c["case_id"] for c in systems[executed[0]]["cases"]]
        by_system = {
            name: {c["case_id"]: c for c in systems[name]["cases"]} for name in executed
        }
        categories = {c["case_id"]: c["category"] for c in systems["marciana"]["cases"]} \
            if "marciana" in executed else {}
        for case_id in case_ids:
            row = [f"`{case_id}`", categories.get(case_id, "")]
            row += [cell(by_system[name][case_id]) for name in executed]
            lines.append("| " + " | ".join(row) + " |")
        lines += ["", f"Legend: {CORRECT} correct · {FAILED} failed (finding) · "
                  f"{UNSUPPORTED} unsupported (declared)."]

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "reports/marciana-adversarial-v1-comparative.json"
    )
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("docs/RESULTS.md")
    report = json.loads(report_path.read_text())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(report), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
