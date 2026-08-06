"""Small, dependency-free metrics used by the Marciana memory benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable, Sequence


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    expected_ids: tuple[str, ...]
    returned_ids: tuple[str, ...]
    redacted_ids: tuple[str, ...]
    latency_us: float
    context_tokens: int

    @property
    def correct(self) -> bool:
        return self.expected_ids == self.returned_ids


def percentile(values: Sequence[float], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((percentage / 100) * (len(ordered) - 1))))
    return ordered[index]


def summarize(results: Iterable[CaseResult]) -> dict[str, float | int]:
    rows = list(results)
    latencies = [row.latency_us for row in rows]
    return {
        "cases": len(rows),
        "accuracy": (sum(row.correct for row in rows) / len(rows)) if rows else 0.0,
        "redaction_leaks": sum(
            bool(set(row.redacted_ids) & set(row.returned_ids)) for row in rows
        ),
        "mean_context_tokens": (
            sum(row.context_tokens for row in rows) / len(rows) if rows else 0.0
        ),
        "p50_latency_us": median(latencies) if latencies else 0.0,
        "p95_latency_us": percentile(latencies, 95),
        "p99_latency_us": percentile(latencies, 99),
    }
