#!/usr/bin/env python3
"""Validate vendor notes: schema, word cap, details link, verification flag.

Run in CI and locally: ``python3 scripts/check_vendor_notes.py``. Every
``vendor-notes/*.md`` (except README/TEMPLATE) must carry well-formed
frontmatter for a known system, a body of at most 100 words, and a
``details:`` link; ``verified: true`` is a maintainer-only act, so this check
never requires it — but a malformed or oversized note fails the build whether
verified or not. Stdlib only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "vendor-notes"
SKIP = {"README.md", "TEMPLATE.md"}

KNOWN_SYSTEMS = {
    "marciana", "marciana-agent", "memfs-agent",
    "mem0", "graphiti", "cognee", "cognee-rs",
    "letta", "letta-direct", "letta-agent", "akka-fluree",
}
KNOWN_BENCHMARKS = {"MARCIANA-ADVERSARIAL"}
KNOWN_VERSIONS = {"v1", "v2"}
REQUIRED = ("system", "benchmark", "versions", "subject", "author", "role",
            "contact", "details", "verified", "date")
MAX_BODY_WORDS = 100
MAX_SUBJECT_CHARS = 80


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter opener")
    closing = text.index("\n---\n", 4)
    head, body = text[4:closing], text[closing + 5 :]
    fields: dict[str, object] = {}
    for line in head.splitlines():
        if not line.strip() or line.startswith("#") or line.startswith(" "):
            continue
        key, _, raw = line.partition(":")
        value = raw.strip().strip('"')
        if value.startswith("[") and value.endswith("]"):
            items = [item.strip().strip('"') for item in value[1:-1].split(",")]
            fields[key.strip()] = [item for item in items if item]
        elif value in ("true", "false"):
            fields[key.strip()] = value == "true"
        else:
            fields[key.strip()] = value
    return fields, body


def check_note(path: Path) -> list[str]:
    problems: list[str] = []
    fields, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    for key in REQUIRED:
        if key not in fields:
            problems.append(f"missing frontmatter field: {key}")
    system = str(fields.get("system", ""))
    if system not in KNOWN_SYSTEMS:
        problems.append(f"unknown system: {system!r}")
    if path.stem != system:
        problems.append(f"filename {path.name} must be {system}.md")
    if str(fields.get("benchmark", "")) not in KNOWN_BENCHMARKS:
        problems.append(f"unknown benchmark: {fields.get('benchmark')!r}")
    versions = fields.get("versions", [])
    if not versions or not set(map(str, versions)) <= KNOWN_VERSIONS:
        problems.append(f"versions must be a non-empty subset of {sorted(KNOWN_VERSIONS)}")
    subject = str(fields.get("subject", ""))
    if not subject or len(subject) > MAX_SUBJECT_CHARS:
        problems.append(f"subject must be 1..{MAX_SUBJECT_CHARS} chars")
    details = str(fields.get("details", ""))
    if not details:
        problems.append("details link is required (in-repo path or https URL)")
    elif details.startswith("http"):
        if not re.match(r"^https://", details):
            problems.append("external details link must be https")
    else:
        if not (ROOT / details).is_file():
            problems.append(f"details file not found in repo: {details}")
    if not isinstance(fields.get("verified"), bool):
        problems.append("verified must be true or false")
    words = len(re.findall(r"\S+", body))
    if words > MAX_BODY_WORDS:
        problems.append(f"body is {words} words; the cap is {MAX_BODY_WORDS}")
    if not words:
        problems.append("body is empty")
    return problems


def main() -> int:
    failures = 0
    notes = [p for p in sorted(NOTES.glob("*.md")) if p.name not in SKIP]
    for path in notes:
        try:
            problems = check_note(path)
        except Exception as error:  # noqa: BLE001 - report as a finding
            problems = [f"unparseable: {error}"]
        for problem in problems:
            print(f"{path.relative_to(ROOT)}: {problem}", file=sys.stderr)
        failures += len(problems)
    print(f"vendor notes checked: {len(notes)} file(s), {failures} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
