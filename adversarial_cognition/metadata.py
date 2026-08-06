"""Strict provider-neutral metadata for reproducible benchmark reports."""

from __future__ import annotations

from dataclasses import dataclass

MAX_METADATA_TEXT = 256


@dataclass(frozen=True)
class BenchmarkMetadata:
    model: str
    provider: str
    embedding: str
    prompt: str
    profile: str
    hardware: str
    revision: str

    def __post_init__(self) -> None:
        values = (
            self.model,
            self.provider,
            self.embedding,
            self.prompt,
            self.profile,
            self.hardware,
            self.revision,
        )
        if any(
            not value or len(value) > MAX_METADATA_TEXT or "\n" in value
            for value in values
        ):
            raise ValueError("benchmark metadata is invalid")

    def as_dict(self) -> dict[str, str]:
        return {
            "model": self.model,
            "provider": self.provider,
            "embedding": self.embedding,
            "prompt": self.prompt,
            "profile": self.profile,
            "hardware": self.hardware,
            "revision": self.revision,
        }

