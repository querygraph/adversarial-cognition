"""Run the MARCIANA-ADVERSARIAL-v1 benchmark and emit a bounded JSON report."""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from pathlib import Path

from adversarial_cognition.adapters import EXTERNAL_SYSTEMS, execute_marciana, execute_systems
from adversarial_cognition.backend import AdversarialBackend
from adversarial_cognition.cases import cases
from adversarial_cognition.corpora import inventory
from adversarial_cognition.report import (
    build_report,
    corpus_digest,
    corpus_manifest,
    receipt_mismatches,
)
from adversarial_cognition.metadata import BenchmarkMetadata

DEFAULT_CORPUS = Path(__file__).resolve().parent / "fixtures" / "marciana-adversarial-v1"
ALL_SYSTEMS = ("marciana",) + tuple(system for system, _ in EXTERNAL_SYSTEMS)


def pin_corpus(corpus_dir: Path) -> str:
    """Write the versioned manifest fixture for the code-defined corpus."""

    manifest = corpus_manifest(cases())
    digest_value = corpus_digest(manifest)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    payload = {"digest": digest_value, "manifest": manifest}
    (corpus_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return digest_value


def verify_corpus(corpus_dir: Path) -> str:
    """Check the code-defined corpus against its versioned manifest fixture."""

    manifest = corpus_manifest(cases())
    digest_value = corpus_digest(manifest)
    pinned = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    if pinned != {"digest": digest_value, "manifest": manifest}:
        raise SystemExit(
            "adversarial corpus does not match its versioned manifest; "
            "regenerate fixtures/marciana-adversarial-v1/manifest.json"
        )
    return digest_value


def measure_lifecycle_us(repeats: int) -> tuple[float, float]:
    """Time corpus formation (seed) and restart on the reference backend."""

    started = time.perf_counter_ns()
    for _ in range(repeats):
        backend = AdversarialBackend()
        backend.seed()
    formation_us = (time.perf_counter_ns() - started) / 1_000 / repeats
    started = time.perf_counter_ns()
    for _ in range(repeats):
        backend.restart()
    restart_us = (time.perf_counter_ns() - started) / 1_000 / repeats
    return formation_us, restart_us


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--systems", default="all")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--model", default="reference-smoke-v1")
    parser.add_argument("--provider", default="local")
    parser.add_argument("--embedding", default="none")
    parser.add_argument("--prompt", default="none")
    parser.add_argument("--profile", default="adversarial-v1")
    parser.add_argument("--revision", default="working-tree")
    parser.add_argument("--json", type=Path, default=Path("reports/marciana-adversarial-v1.json"))
    parser.add_argument(
        "--pin-corpus",
        action="store_true",
        help="write the versioned corpus manifest fixture and exit",
    )
    args = parser.parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be positive")
    if args.pin_corpus:
        print(f"pinned corpus digest: {pin_corpus(args.corpus)}")
        return
    selected = ALL_SYSTEMS if args.systems == "all" else tuple(args.systems.split(","))
    metadata = BenchmarkMetadata(
        model=args.model,
        provider=args.provider,
        embedding=args.embedding,
        prompt=args.prompt,
        profile=args.profile,
        hardware=platform.platform(),
        revision=args.revision,
    )
    suite = cases()
    manifest_digest = verify_corpus(args.corpus)
    systems = execute_systems(selected, suite, args.repeats, dict(os.environ))
    mismatches = 0
    if "marciana" in selected:
        # Receipt determinism is a hard gate: two identical runs must agree.
        mismatches = receipt_mismatches(
            execute_marciana(suite, 1).outcomes, execute_marciana(suite, 1).outcomes
        )
    formation_us, restart_us = measure_lifecycle_us(args.repeats)
    report = build_report(
        metadata.as_dict(),
        manifest_digest,
        systems,
        mismatches,
        formation_us,
        restart_us,
        inventory(dict(os.environ)),
    )
    output = json.dumps(report, indent=2, sort_keys=True)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(output + "\n", encoding="utf-8")
    gates = ", ".join(f"{name}={count}" for name, count in sorted(report["hard_gates"].items()))
    statuses = ", ".join(
        f"{name}={entry['status']}" for name, entry in sorted(report["systems"].items())
    )
    print(f"{report['benchmark']}: {report['status']}")
    print(f"systems: {statuses}")
    print(f"hard gates: {gates}")
    print(f"report: {args.json}")
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
