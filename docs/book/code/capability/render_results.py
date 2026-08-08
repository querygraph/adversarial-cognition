"""Render a CAPABILITY-ADVERSARIAL-v1 report into a Markdown results document."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from capability_adversarial.cases import cases

CORRECT, FAILED, UNSUPPORTED = "✓", "✗", "·"


def render(report: dict) -> str:
    systems = report["systems"]
    order = ["reference", "typesec", "ucan", "biscuit", "macaroon", "jwt",
             "opa", "cedar", "spicedb", "openfga"]
    present = [s for s in sorted(systems, key=lambda s: order.index(s["system"])
                                 if s["system"] in order else 99)]
    executed = [s for s in present if s.get("status") == "executed"]

    lines = [
        "# CAPABILITY-ADVERSARIAL-v1 results",
        "",
        f"**Benchmark:** {report['benchmark']}  ",
        f"**Corpus digest:** `{report['corpus_digest']}`  ",
        f"**Overall status:** {report['status']}",
        "",
        "Each system is scored only on the capabilities it declares. A cell is "
        "✓ when the system produced the correct authorization outcome, ✗ when "
        "it did not (a finding), and · when the system honestly does not claim "
        "that capability — never scored as a pass or a failure.",
        "",
        "## Systems",
        "",
        "| System | Status | Supported | Correct | Unsupported | Gate violations |",
        "|--------|--------|:---------:|:-------:|:-----------:|:---------------:|",
    ]
    for s in present:
        if s.get("status") == "executed":
            summary = s["summary"]
            gv = sum(s["hard_gates"].values())
            lines.append(f"| {s['system']} | {s.get('result','executed')} | "
                         f"{summary['supported']} | {summary['correct']} | "
                         f"{summary['unsupported']} | {gv} |")
        else:
            detail = ", ".join(s.get("missing_configuration", ())) or s.get("error", "")
            lines.append(f"| {s['system']} | {s['status']} | — | — | — | {detail} |")

    if executed:
        lines += ["", "## Case matrix", "",
                  "| Case | Capability | " + " | ".join(s["system"] for s in executed) + " |",
                  "|------|-----------|" + "|".join(["---"] * len(executed)) + "|"]
        by = {s["system"]: {row["case_id"]: row for row in s["cases"]} for s in executed}
        for case in cases():
            row = [f"`{case.case_id}`", case.capability]
            for s in executed:
                r = by[s["system"]][case.case_id]
                cell = UNSUPPORTED if not r["supported"] else (CORRECT if r["correct"] else FAILED)
                row.append(cell)
            lines.append("| " + " | ".join(row) + " |")
        lines += ["", f"Legend: {CORRECT} correct · {FAILED} failed (finding) · "
                  f"{UNSUPPORTED} not claimed."]
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/capability-adversarial-v1.json")
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("out/RESULTS.md")
    report = json.loads(report_path.read_text())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(report), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
