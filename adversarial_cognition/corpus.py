"""Pinned, content-local benchmark corpus contracts.

Adapters normalize an external dataset into this small schema. They never
download data implicitly: callers provide an authorized local JSONL path and
an exact source pin for reproducibility.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

SHA1 = re.compile(r"^[0-9a-f]{40}$")
MAX_CASES = 100_000
MAX_ID = 256
MAX_QUERY = 16_384


@dataclass(frozen=True)
class SourcePin:
    name: str
    url: str
    revision: str
    schema: str

    def validate(self) -> None:
        if not self.name or not self.url.startswith("https://") or not SHA1.fullmatch(self.revision):
            raise ValueError("benchmark source must have an HTTPS URL and exact revision")
        if not self.schema:
            raise ValueError("benchmark source schema is required")


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    query: str
    as_of: date
    expected_ids: tuple[str, ...]
    abstain: bool = False


def load_cases(path: Path, source: SourcePin) -> tuple[EvaluationCase, ...]:
    """Load normalized JSONL cases from an authorized local fixture.

    Each line contains ``case_id``, ``query``, ``as_of`` (ISO date), and
    ``expected_ids``. The loader is deliberately strict so malformed or
    duplicate cases cannot silently distort a release benchmark.
    """

    source.validate()
    cases: list[EvaluationCase] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            case_id = row["case_id"]
            query = row["query"]
            as_of = date.fromisoformat(row["as_of"])
            expected_ids = tuple(row["expected_ids"])
            abstain = bool(row.get("abstain", False))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid benchmark case at line {line_number}") from error
        if (
            not isinstance(case_id, str)
            or not case_id
            or len(case_id) > MAX_ID
            or case_id in seen
            or not isinstance(query, str)
            or not query
            or len(query) > MAX_QUERY
            or any(not isinstance(identifier, str) or not identifier or len(identifier) > MAX_ID
                   for identifier in expected_ids)
        ):
            raise ValueError(f"invalid benchmark case at line {line_number}")
        seen.add(case_id)
        cases.append(EvaluationCase(case_id, query, as_of, expected_ids, abstain))
        if len(cases) > MAX_CASES:
            raise ValueError("benchmark corpus exceeds its fixed case bound")
    if not cases:
        raise ValueError("benchmark corpus is empty")
    return tuple(cases)
