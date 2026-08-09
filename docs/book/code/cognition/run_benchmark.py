"""Run the MARCIANA-ADVERSARIAL benchmark and emit a bounded JSON report.

``--benchmark v1`` (the default — the published benchmark, byte-stable) or
``--benchmark v2`` (two tracks, authenticated identities, its own corpus
digest). Every version-dependent choice — case suite, reference runner,
corpus fixture, system registry, report version, output path — is selected
here from that one flag.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from pathlib import Path

from adversarial_cognition.adapters import (
    execute_marciana,
    execute_systems,
    external_systems,
)
from adversarial_cognition.backend import AdversarialBackend
from adversarial_cognition.cases import cases, run_case
from adversarial_cognition.cases_v2 import cases_v2, run_case_v2
from adversarial_cognition.corpora import inventory
from adversarial_cognition.report import (
    BENCHMARK,
    BENCHMARK_V2,
    build_report,
    corpus_digest,
    corpus_manifest,
    corpus_manifest_v2,
    receipt_mismatches,
)
from adversarial_cognition.metadata import BenchmarkMetadata

FIXTURES = Path(__file__).resolve().parent / "fixtures"

VERSIONS = {
    "v1": {
        "number": 1,
        "benchmark": BENCHMARK,
        "suite": cases,
        "runner": run_case,
        "manifest": corpus_manifest,
        "corpus": FIXTURES / "marciana-adversarial-v1",
        "json": Path("reports/marciana-adversarial-v1.json"),
        "profile": "adversarial-v1",
    },
    "v2": {
        "number": 2,
        "benchmark": BENCHMARK_V2,
        "suite": cases_v2,
        "runner": run_case_v2,
        "manifest": corpus_manifest_v2,
        "corpus": FIXTURES / "marciana-adversarial-v2",
        "json": Path("reports/marciana-adversarial-v2.json"),
        "profile": "adversarial-v2",
    },
}


def pin_corpus(version: dict, corpus_dir: Path) -> str:
    """Write the versioned manifest fixture for the code-defined corpus."""

    manifest = version["manifest"](version["suite"]())
    digest_value = corpus_digest(manifest)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    payload = {"digest": digest_value, "manifest": manifest}
    (corpus_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return digest_value


def verify_corpus(version: dict, corpus_dir: Path) -> str:
    """Check the code-defined corpus against its versioned manifest fixture."""

    manifest = version["manifest"](version["suite"]())
    digest_value = corpus_digest(manifest)
    pinned = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    if pinned != {"digest": digest_value, "manifest": manifest}:
        raise SystemExit(
            "adversarial corpus does not match its versioned manifest; "
            f"regenerate {corpus_dir}/manifest.json"
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
    parser.add_argument("--benchmark", choices=("v1", "v2"), default="v1")
    parser.add_argument("--systems", default="all")
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--model", default="reference-smoke-v1")
    parser.add_argument("--provider", default="local")
    parser.add_argument("--embedding", default="none")
    parser.add_argument("--prompt", default="none")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--revision", default="working-tree")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument(
        "--pin-corpus",
        action="store_true",
        help="write the versioned corpus manifest fixture and exit",
    )
    args = parser.parse_args()
    version = VERSIONS[args.benchmark]
    corpus_dir = args.corpus or version["corpus"]
    json_path = args.json or version["json"]
    profile = args.profile or version["profile"]
    if args.repeats < 1:
        raise SystemExit("--repeats must be positive")
    if args.pin_corpus:
        print(f"pinned corpus digest: {pin_corpus(version, corpus_dir)}")
        return
    all_systems = ("marciana",) + tuple(
        system for system, _ in external_systems(version["number"])
    )
    selected = all_systems if args.systems == "all" else tuple(args.systems.split(","))
    metadata = BenchmarkMetadata(
        model=args.model,
        provider=args.provider,
        embedding=args.embedding,
        prompt=args.prompt,
        profile=profile,
        hardware=platform.platform(),
        revision=args.revision,
    )
    suite = version["suite"]()
    manifest_digest = verify_corpus(version, corpus_dir)
    systems = execute_systems(
        selected, suite, args.repeats, dict(os.environ),
        benchmark_version=version["number"], runner=version["runner"],
    )
    mismatches = 0
    if "marciana" in selected:
        # Receipt determinism is a hard gate: two identical runs must agree.
        mismatches = receipt_mismatches(
            execute_marciana(suite, 1, version["runner"]).outcomes,
            execute_marciana(suite, 1, version["runner"]).outcomes,
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
        benchmark=version["benchmark"],
    )
    output = json.dumps(report, indent=2, sort_keys=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(output + "\n", encoding="utf-8")
    gates = ", ".join(f"{name}={count}" for name, count in sorted(report["hard_gates"].items()))
    statuses = ", ".join(
        f"{name}={entry['status']}" for name, entry in sorted(report["systems"].items())
    )
    print(f"{report['benchmark']}: {report['status']}")
    print(f"systems: {statuses}")
    print(f"hard gates: {gates}")
    print(f"report: {json_path}")
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
