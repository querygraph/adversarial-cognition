"""Render a CATALOG-PROVENANCE-v1 report into a Markdown results document."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from catalog_provenance.cases import cases

CORRECT, FAILED, UNSUPPORTED = "✓", "✗", "·"


def render(report: dict) -> str:
    catalogs = report["catalogs"]
    order = ["reference", "lakecat", "nessie", "gravitino", "polaris"]
    present = [c for c in sorted(catalogs, key=lambda c: order.index(c["catalog"])
                                 if c["catalog"] in order else 99)]
    executed = [c for c in present if c.get("status") == "executed"]

    lines = [
        "# CATALOG-PROVENANCE-v1 results",
        "",
        f"**Benchmark:** {report['benchmark']}  ",
        f"**Corpus digest:** `{report['corpus_digest']}`  ",
        f"**Overall status:** {report['status']}",
        "",
        "Each catalog is scored only on the capabilities it declares. A cell is "
        "✓ when the catalog produced the correct provable-transaction "
        "outcome, ✗ when it did not (a finding), and · when the catalog "
        "honestly does not claim that capability — never scored as a pass or "
        "a failure.",
        "",
        "## Catalogs",
        "",
        "| Catalog | Status | Supported | Correct | Unsupported | Gate violations |",
        "|---------|--------|:---------:|:-------:|:-----------:|:---------------:|",
    ]
    for c in present:
        if c.get("status") == "executed":
            s = c["summary"]
            gv = sum(c["hard_gates"].values())
            lines.append(f"| {c['catalog']} | {c.get('result','executed')} | "
                         f"{s['supported']} | {s['correct']} | {s['unsupported']} | {gv} |")
        else:
            detail = ", ".join(c.get("missing_configuration", ())) or c.get("error", "")
            lines.append(f"| {c['catalog']} | {c['status']} | — | — | — | {detail} |")

    if executed:
        capability = {c.case_id: c.capability for c in cases()}
        lines += ["", "## Case matrix", "",
                  "| Case | Capability | " + " | ".join(c["catalog"] for c in executed) + " |",
                  "|------|-----------|" + "|".join(["---"] * len(executed)) + "|"]
        by = {c["catalog"]: {row["case_id"]: row for row in c["cases"]} for c in executed}
        for case in cases():
            row = [f"`{case.case_id}`", case.capability]
            for c in executed:
                r = by[c["catalog"]][case.case_id]
                cell = UNSUPPORTED if not r["supported"] else (CORRECT if r["correct"] else FAILED)
                row.append(cell)
            lines.append("| " + " | ".join(row) + " |")
        lines += ["", f"Legend: {CORRECT} correct · {FAILED} failed (finding) · "
                  f"{UNSUPPORTED} not claimed."]
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/catalog-provenance-v1.json")
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("out/RESULTS.md")
    report = json.loads(report_path.read_text())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(report), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
