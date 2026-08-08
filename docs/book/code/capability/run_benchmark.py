"""Run CAPABILITY-ADVERSARIAL-v1 and emit a bounded JSON report."""

from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path

from capability_adversarial.adapters import EXTERNAL_SYSTEMS, execute_systems
from capability_adversarial.cases import cases
from capability_adversarial.report import (
    build_report,
    corpus_digest,
    corpus_manifest,
    system_status,
)

DEFAULT_CORPUS = Path(__file__).resolve().parent / "fixtures" / "capability-adversarial-v1"
ALL_SYSTEMS = ("reference",) + tuple(name for name, _ in EXTERNAL_SYSTEMS)


def pin_corpus(corpus_dir: Path) -> str:
    manifest = corpus_manifest(cases())
    digest_value = corpus_digest(manifest)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "manifest.json").write_text(
        json.dumps({"digest": digest_value, "manifest": manifest}, indent=2, sort_keys=True) + "\n")
    return digest_value


def verify_corpus(corpus_dir: Path) -> str:
    manifest = corpus_manifest(cases())
    digest_value = corpus_digest(manifest)
    pinned = json.loads((corpus_dir / "manifest.json").read_text())
    if pinned != {"digest": digest_value, "manifest": manifest}:
        raise SystemExit("corpus does not match its versioned manifest; regenerate with --pin-corpus")
    return digest_value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--systems", default="all")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--json", type=Path, default=Path("reports/capability-adversarial-v1.json"))
    parser.add_argument("--pin-corpus", action="store_true")
    args = parser.parse_args()

    if args.pin_corpus:
        print(f"pinned corpus digest: {pin_corpus(args.corpus)}")
        return

    suite = cases()
    manifest_digest = verify_corpus(args.corpus)
    selected = ALL_SYSTEMS if args.systems == "all" else tuple(args.systems.split(","))
    systems = execute_systems(selected, suite, dict(os.environ))
    for entry in systems:
        if entry.get("status") == "executed":
            entry["result"] = system_status("executed", entry["hard_gates"])

    metadata = {"harness": platform.platform(), "corpus": "capability-adversarial-v1"}
    report = build_report(metadata, manifest_digest, systems)
    output = json.dumps(report, indent=2, sort_keys=True)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(output + "\n")

    print(f"{report['benchmark']}: {report['status']}")
    for entry in systems:
        if entry.get("status") == "executed":
            s = entry["summary"]
            gates = sum(entry["hard_gates"].values())
            print(f"  {entry['system']:10} {entry.get('result','?'):5} | "
                  f"supported {s['supported']}, correct {s['correct']}, "
                  f"unsupported {s['unsupported']} | gate violations {gates}")
        else:
            detail = ", ".join(entry.get("missing_configuration", ())) or entry.get("error", "")
            print(f"  {entry['system']:10} {entry['status']} | {detail}")
    print(f"report: {args.json}")
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
