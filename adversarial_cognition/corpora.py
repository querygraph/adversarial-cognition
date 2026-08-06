"""Offline-only public-corpus inventory for MARCIANA-ADVERSARIAL-v1.

Public corpora are optional, pinned, and never downloaded. Each corpus is
normalized only when its local fixture path is explicitly configured;
otherwise it is inventoried as ``unavailable`` with the missing
configuration named. Answer-quality execution against these corpora is a
native-service concern and is never simulated by the reference backend.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .public_loaders import (
    BEAM_SOURCE,
    LOCOMO_SOURCE,
    LONGMEMEVAL_SOURCE,
    load_beam_parquet,
    load_locomo,
    load_longmemeval,
)
from .corpus import EvaluationCase, SourcePin, load_cases

DMR_SOURCE = SourcePin(
    "dmr-msc-self-instruct",
    "https://huggingface.co/datasets/MemGPT/MSC-Self-Instruct",
    "5138f416f8fa76b75b2e080da87e8a8e346e1500",
    "normalized-jsonl-v1",
)
LETTA_EVALS_SOURCE = SourcePin(
    "letta-evals",
    "https://github.com/letta-ai/letta-evals.git",
    "80a097d8519590c0f7827be1940ace0b8d1ebabb",
    "normalized-jsonl-v1",
)


def load_dmr(path: Path) -> tuple[EvaluationCase, ...]:
    """Load DMR cases normalized offline to the strict JSONL contract."""

    return load_cases(path, DMR_SOURCE)


def load_letta_evals(path: Path) -> tuple[EvaluationCase, ...]:
    """Load Letta-Evals cases normalized offline to the strict JSONL contract."""

    return load_cases(path, LETTA_EVALS_SOURCE)


PUBLIC_CORPORA = (
    ("locomo", "MARCIANA_ADVERSARIAL_LOCOMO_PATH", LOCOMO_SOURCE, load_locomo),
    ("longmemeval", "MARCIANA_ADVERSARIAL_LONGMEMEVAL_PATH", LONGMEMEVAL_SOURCE, load_longmemeval),
    ("beam", "MARCIANA_ADVERSARIAL_BEAM_PATH", BEAM_SOURCE, load_beam_parquet),
    ("dmr", "MARCIANA_ADVERSARIAL_DMR_PATH", DMR_SOURCE, load_dmr),
    ("letta-evals", "MARCIANA_ADVERSARIAL_LETTA_EVALS_PATH", LETTA_EVALS_SOURCE, load_letta_evals),
)


def inventory(environ: dict[str, str]) -> dict[str, object]:
    """Classify every public corpus as normalized, error, or unavailable."""

    report: dict[str, object] = {}
    for name, path_variable, source, loader in PUBLIC_CORPORA:
        entry: dict[str, object] = {
            "source": source.name,
            "url": source.url,
            "revision": source.revision,
            "schema": source.schema,
        }
        configured = environ.get(path_variable, "").strip()
        if not configured:
            entry["status"] = "unavailable"
            entry["missing_configuration"] = [path_variable]
        else:
            try:
                path = Path(configured)
                cases = loader(path)
                entry["status"] = "normalized"
                entry["cases"] = len(cases)
                entry["file_digest"] = (
                    "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                )
            except Exception as error:  # noqa: BLE001 - loader failures become reportable
                entry["status"] = "error"
                entry["error"] = str(error)[:256]
        report[name] = entry
    return report
