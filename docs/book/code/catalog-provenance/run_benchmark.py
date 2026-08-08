"""Run CATALOG-PROVENANCE-v1 and emit a bounded JSON report."""

from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path

from catalog_provenance.adapters import EXTERNAL_CATALOGS, execute_catalogs
from catalog_provenance.cases import cases
from catalog_provenance.report import (
    build_report,
    catalog_status,
    corpus_digest,
    corpus_manifest,
)

DEFAULT_CORPUS = Path(__file__).resolve().parent / "fixtures" / "catalog-provenance-v1"
ALL_CATALOGS = ("reference",) + tuple(name for name, _ in EXTERNAL_CATALOGS)


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
    parser.add_argument("--catalogs", default="all")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--json", type=Path, default=Path("reports/catalog-provenance-v1.json"))
    parser.add_argument("--pin-corpus", action="store_true")
    args = parser.parse_args()

    if args.pin_corpus:
        print(f"pinned corpus digest: {pin_corpus(args.corpus)}")
        return

    suite = cases()
    manifest_digest = verify_corpus(args.corpus)
    selected = ALL_CATALOGS if args.catalogs == "all" else tuple(args.catalogs.split(","))
    catalogs = execute_catalogs(selected, suite, dict(os.environ))
    for entry in catalogs:
        if entry.get("status") == "executed":
            entry["result"] = catalog_status("executed", entry["hard_gates"])

    metadata = {"harness": platform.platform(), "corpus": "catalog-provenance-v1"}
    report = build_report(metadata, manifest_digest, catalogs)
    output = json.dumps(report, indent=2, sort_keys=True)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(output + "\n")

    print(f"{report['benchmark']}: {report['status']}")
    for entry in catalogs:
        if entry.get("status") == "executed":
            s = entry["summary"]
            gates = sum(entry["hard_gates"].values())
            print(f"  {entry['catalog']:10} {entry.get('result','?'):5} | "
                  f"supported {s['supported']}, correct {s['correct']}, "
                  f"unsupported {s['unsupported']} | gate violations {gates}")
        else:
            detail = ", ".join(entry.get("missing_configuration", ())) or entry.get("error", "")
            print(f"  {entry['catalog']:10} {entry['status']} | {detail}")
    print(f"report: {args.json}")
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
