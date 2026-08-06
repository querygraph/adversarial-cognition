"""Local adapters for the released LoCoMo and LongMemEval layouts."""

from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path

from .corpus import EvaluationCase, SourcePin

LOCOMO_SOURCE = SourcePin(
    "locomo10",
    "https://github.com/snap-research/locomo.git",
    "3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376",
    "locomo10-qa-v1",
)
LONGMEMEVAL_SOURCE = SourcePin(
    "longmemeval-cleaned",
    "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned",
    "98d7416c24c778c2fee6e6f3006e7a073259d48f",
    "longmemeval-question-v1",
)
BEAM_SOURCE = SourcePin(
    "beam",
    "https://huggingface.co/datasets/Mohammadta/BEAM",
    "3205395e897e7318c7b094ef4e6047b9b82dbb03",
    "beam-parquet-v1",
)
BEAM_10M_SOURCE = SourcePin(
    "beam-10m",
    "https://huggingface.co/datasets/Mohammadta/BEAM-10M",
    "9b2096193fe74e2837e4713e483351e19817773c",
    "beam-parquet-v1",
)


def load_locomo(path: Path, as_of: date = date.max) -> tuple[EvaluationCase, ...]:
    """Normalize LoCoMo QA annotations from an authorized local JSON file."""

    rows = json.loads(path.read_text(encoding="utf-8"))
    cases: list[EvaluationCase] = []
    for sample_index, sample in enumerate(rows):
        for qa_index, annotation in enumerate(sample.get("qa", [])):
            evidence = tuple(annotation.get("evidence") or ())
            cases.append(
                EvaluationCase(
                    case_id=f"locomo:{sample_index}:{qa_index}",
                    query=annotation["question"],
                    as_of=as_of,
                    expected_ids=evidence,
                    abstain=not bool(evidence),
                )
            )
    if not cases:
        raise ValueError("LoCoMo corpus has no QA annotations")
    return tuple(cases)


def load_longmemeval(path: Path) -> tuple[EvaluationCase, ...]:
    """Normalize LongMemEval question records from an authorized local JSON."""

    rows = json.loads(path.read_text(encoding="utf-8"))
    cases: list[EvaluationCase] = []
    for row in rows:
        question_id = row["question_id"]
        question_date = date.fromisoformat(row["question_date"][:10])
        evidence = tuple(row.get("answer_session_ids") or ())
        cases.append(
            EvaluationCase(
                case_id=f"longmemeval:{question_id}",
                query=row["question"],
                as_of=question_date,
                expected_ids=evidence,
                abstain=question_id.endswith("_abs"),
            )
        )
    if not cases:
        raise ValueError("LongMemEval corpus is empty")
    return tuple(cases)


def normalize_beam_row(row: dict[str, object]) -> tuple[EvaluationCase, ...]:
    """Normalize one BEAM row without retaining the long conversation text.

    BEAM questions do not expose a canonical as-of field or per-answer source
    IDs. The conversation ID is therefore the bounded retrieval target and
    ``date.max`` is used explicitly for the as-of value.
    """

    conversation_id = str(row["conversation_id"])
    encoded = row.get("probing_questions", "")
    questions = ast.literal_eval(encoded) if isinstance(encoded, str) else encoded
    cases: list[EvaluationCase] = []
    for category, entries in (questions or {}).items():
        for index, entry in enumerate(entries or ()):
            if not isinstance(entry, dict) or not entry.get("question"):
                continue
            cases.append(
                EvaluationCase(
                    case_id=f"beam:{conversation_id}:{category}:{index}",
                    query=str(entry["question"]),
                    as_of=date.max,
                    expected_ids=(conversation_id,),
                    abstain=str(category).lower() == "abstention",
                )
            )
    if not cases:
        raise ValueError("BEAM row has no probing questions")
    return tuple(cases)


def load_beam_parquet(path: Path) -> tuple[EvaluationCase, ...]:
    """Load BEAM Parquet through optional PyArrow, kept out of core deps."""

    try:
        import pyarrow.parquet as parquet
    except ImportError as error:
        raise RuntimeError("BEAM Parquet loading requires the optional pyarrow dependency") from error
    table = parquet.read_table(path, columns=["conversation_id", "probing_questions"])
    cases = tuple(case for row in table.to_pylist() for case in normalize_beam_row(row))
    if not cases:
        raise ValueError("BEAM corpus is empty")
    return cases
