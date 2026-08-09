"""Render a comparative benchmark report into a Markdown results document.

Reads the JSON emitted by run_comparative.sh and writes the results document.
v1 reports render as the single ranked table published in docs/RESULTS.md —
that path is frozen byte-for-byte (tests/test_render_golden.py). v2 reports
render one section per track (memory-store, agent-memory), each with its own
systems table and case matrix, compared only within the track; the renderer
enforces that no rendered table mixes tracks rather than relying on a caption.
Cells use ✓ (correct), ✗ (failed, a finding about that system), and · (the
system honestly declared the case unsupported).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from adversarial_cognition.tracks import (
    AGENT_MEMORY,
    MEMORY_STORE,
    TRACKS,
    track_for_interface,
)

CORRECT, FAILED, UNSUPPORTED = "✓", "✗", "·"

TRACK_TITLES = {
    MEMORY_STORE: "Memory-store track",
    AGENT_MEMORY: "Agent-memory track",
}
TRACK_NOTES = {
    MEMORY_STORE: (
        "Storage, retrieval, deletion, temporal, and authorization APIs are "
        "called directly. Systems in this table are compared only with each "
        "other, never with the agent-memory track."
    ),
    AGENT_MEMORY: (
        "Memory is reached through one shared agent loop — same model, same "
        "prompts, same tool contract, same context budget for every backend; "
        "only the memory varies. Systems in this table are compared only with "
        "each other, never with the memory-store track."
    ),
}


def cell(case: dict) -> str:
    if not case.get("supported", True):
        return UNSUPPORTED
    return CORRECT if case["correct"] else FAILED


def render_v1(report: dict) -> str:
    systems = report["systems"]
    def ranking_key(name: str) -> tuple:
        entry = systems[name]
        if entry["status"] != "executed":
            return (2, 0.0, 0, 0, name)
        supported = [case for case in entry["cases"] if case.get("supported", True)]
        correct = sum(case["correct"] for case in supported)
        accuracy = correct / len(supported) if supported else 0.0
        # Marciana is the reference baseline; the remaining systems are
        # ordered by diagnostic accuracy, then coverage, not adapter order.
        reference = 0 if name == "marciana" else 1
        return (reference, -accuracy, -len(supported), -correct, name)

    present = sorted(systems, key=ranking_key)
    executed = [name for name in present if systems[name]["status"] == "executed"]

    lines = [
        "# MARCIANA-ADVERSARIAL-v1 comparative results",
        "",
        f"**Benchmark:** {report['benchmark']}",
        f"**Corpus digest:** `{report['corpus_digest']}`",
        f"**Overall status:** {report['status']}",
        f"**Profile:** {report['metadata'].get('profile', '')} on "
        f"{report['metadata'].get('provider', '')}",
        "",
        "Comparative systems run through their own OSS stacks with local models "
        "(Ollama) and local infrastructure. A cell is ✓ when the system produced "
        "the correct outcome, ✗ when it did not (a finding about that system), and "
        "· when the system honestly declared the case unsupported — never scored "
        "as a pass or a failure. Correctness is shown together with coverage; "
        "scores over different coverage are not directly comparable.",
        "",
        "## Systems",
        "",
        "| System | Status | Interface | Adapter | Coverage | Correctness within coverage |",
        "|--------|--------|-----------|---------|----------|-----------------------------|",
    ]
    for name in present:
        entry = systems[name]
        status = entry["status"]
        if status == "executed":
            cases = entry["cases"]
            supported = [c for c in cases if c.get("supported", True)]
            acc = sum(c["correct"] for c in supported) / len(supported) if supported else 0.0
            lines.append(
                f"| {name} | executed | {entry.get('interface', '—')} | "
                f"`{entry['adapter_version']}` | "
                f"{len(supported)}/{len(cases)} | "
                f"{acc:.0%} ({sum(c['correct'] for c in supported)}/{len(supported)}) |"
            )
        else:
            missing = ", ".join(entry.get("missing_configuration", ())) or entry.get("error", "")
            lines.append(f"| {name} | {status} | — | — | — | {missing} |")

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


def _system_tracks(report: dict) -> dict[str, str]:
    """Map every executed system to its track (report-stamped or derived)."""

    tracks: dict[str, str] = {}
    for name, entry in report["systems"].items():
        if entry.get("status") == "executed":
            tracks[name] = entry.get(
                "track", track_for_interface(entry.get("interface", "direct-api"))
            )
    return tracks


def assert_no_cross_track_table(markdown: str, report: dict) -> None:
    """Fail if any rendered table mentions systems from two different tracks.

    The v2 rule — compared only within a track — is enforced structurally:
    every markdown table is parsed, every cell that names an executed system is
    resolved to its track, and a table naming systems from more than one track
    is an error, not a caption problem.
    """

    tracks = _system_tracks(report)
    table: list[str] = []

    def check(rows: list[str]) -> None:
        seen: set[str] = set()
        for row in rows:
            for raw in row.strip().strip("|").split("|"):
                token = raw.strip().strip("`")
                if token in tracks:
                    seen.add(tracks[token])
        if len(seen) > 1:
            raise ValueError(
                "rendered table mixes tracks: " + ", ".join(sorted(seen))
            )

    for line in markdown.splitlines() + [""]:
        if line.lstrip().startswith("|"):
            table.append(line)
        elif table:
            check(table)
            table = []


def render_v2(report: dict) -> str:
    systems = report["systems"]
    tracks = _system_tracks(report)

    def ranking_key(name: str) -> tuple:
        entry = systems[name]
        supported = [case for case in entry["cases"] if case.get("supported", True)]
        correct = sum(case["correct"] for case in supported)
        accuracy = correct / len(supported) if supported else 0.0
        reference = 0 if name.startswith("marciana") else 1
        return (reference, -accuracy, -len(supported), -correct, name)

    lines = [
        "# MARCIANA-ADVERSARIAL-v2 comparative results",
        "",
        f"**Benchmark:** {report['benchmark']}",
        f"**Corpus digest:** `{report['corpus_digest']}`",
        f"**Overall status:** {report['status']}",
        f"**Profile:** {report['metadata'].get('profile', '')} on "
        f"{report['metadata'].get('provider', '')}",
        "",
        "v2 separates systems by how their memory is reached and compares only "
        "within a track. The memory-store track calls each system's storage API "
        "directly; the agent-memory track drives every backend through one "
        "shared, controlled agent loop. A cell is ✓ when the system produced "
        "the correct outcome, ✗ when it did not (a finding about that system), "
        "and · when the case is unsupported — declared by the system, or "
        "inexpressible in the shared tool contract for the whole track. "
        "Correctness is shown together with coverage; scores over different "
        "coverage are not directly comparable, and scores across tracks are "
        "never comparable.",
    ]

    for track in TRACKS:
        members = sorted(
            (name for name, assigned in tracks.items() if assigned == track),
            key=ranking_key,
        )
        if not members:
            continue
        lines += ["", f"## {TRACK_TITLES[track]}", "", TRACK_NOTES[track], ""]

        harness = next(
            (systems[name].get("harness") for name in members
             if systems[name].get("harness")),
            None,
        )
        if harness:
            lines += [
                "**Shared harness:** model `{model}` · seed {seed} · "
                "temperature {temperature} · num_ctx {num_ctx} · "
                "max turns {max_turns} · prompts `{prompt_digest}` · "
                "tools `{tool_contract}`".format(**harness),
                "",
            ]

        lines += [
            "| System | Adapter | Coverage | Correctness within coverage |",
            "|--------|---------|----------|-----------------------------|",
        ]
        for name in members:
            entry = systems[name]
            cases = entry["cases"]
            supported = [c for c in cases if c.get("supported", True)]
            acc = sum(c["correct"] for c in supported) / len(supported) if supported else 0.0
            lines.append(
                f"| {name} | `{entry['adapter_version']}` | "
                f"{len(supported)}/{len(cases)} | "
                f"{acc:.0%} ({sum(c['correct'] for c in supported)}/{len(supported)}) |"
            )

        lines += ["", f"### Case matrix — {TRACK_TITLES[track].lower()}", "",
                  "| Case | Category | " + " | ".join(members) + " |",
                  "|------|----------|" + "|".join(["---"] * len(members)) + "|"]
        case_ids = [c["case_id"] for c in systems[members[0]]["cases"]]
        by_system = {
            name: {c["case_id"]: c for c in systems[name]["cases"]} for name in members
        }
        reference = next(
            (name for name in members if name.startswith("marciana")), members[0]
        )
        categories = {
            c["case_id"]: c["category"] for c in systems[reference]["cases"]
        }
        for case_id in case_ids:
            row = [f"`{case_id}`", categories.get(case_id, "")]
            row += [cell(by_system[name][case_id]) for name in members]
            lines.append("| " + " | ".join(row) + " |")

    lines += ["", "## Hard gates (Marciana reference)", ""]
    lines.append("| Gate | Count |")
    lines.append("|------|-------|")
    for gate, count in sorted(report["hard_gates"].items()):
        lines.append(f"| `{gate}` | {count} |")

    absent = sorted(
        name for name, entry in systems.items() if entry.get("status") != "executed"
    )
    if absent:
        lines += ["", "## Not executed", "",
                  "| System | Status | Detail |",
                  "|--------|--------|--------|"]
        for name in absent:
            entry = systems[name]
            missing = ", ".join(entry.get("missing_configuration", ())) or entry.get("error", "")
            lines.append(f"| {name} | {entry['status']} | {missing} |")

    lines += ["", f"Legend: {CORRECT} correct · {FAILED} failed (finding) · "
              f"{UNSUPPORTED} unsupported (declared or track-inexpressible).", ""]
    rendered = "\n".join(lines)
    assert_no_cross_track_table(rendered, report)
    return rendered


def render(report: dict) -> str:
    benchmark = report["benchmark"]
    if benchmark.endswith("-v1"):
        return render_v1(report)
    if benchmark.endswith("-v2"):
        return render_v2(report)
    raise ValueError(f"unknown benchmark version: {benchmark}")


def main() -> None:
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "reports/marciana-adversarial-v1-comparative.json"
    )
    report = json.loads(report_path.read_text())
    default_out = (
        Path("docs/RESULTS-v2.md")
        if report["benchmark"].endswith("-v2")
        else Path("docs/RESULTS.md")
    )
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(report), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
