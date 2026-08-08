#!/usr/bin/env python3
"""Neutralize vault-incompatible relative links in vendored code snapshots.

The benchmark repositories ship GitHub-flavored READMEs whose relative links
point at directories (`adapters/foo/`) and at paths excluded from the snapshot
(`docs/…`, `outputs/`). Inside an Obsidian vault those resolve to nothing, so
they read as broken navigation. This pass rewrites any *relative* Markdown link
or image whose target is not a real file in the snapshot into its plain link
text, leaving working links, code fences, and external URLs untouched.

Run by `vendor.sh` after copying; safe to re-run (idempotent).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
KEEP_PREFIXES = ("http://", "https://", "mailto:", "obsidian:", "firstpair:", "#", "//")


def _resolves(md_file: Path, target: str) -> bool:
    raw = target.strip().removeprefix("<").removesuffix(">")
    raw = raw.split("#", 1)[0].split("?", 1)[0].strip()
    if not raw or raw.lower().startswith(KEEP_PREFIXES):
        return True  # external / anchor / already-inert — leave it alone
    try:
        return (md_file.parent / raw).resolve().is_file()
    except (OSError, ValueError):
        return False


def _sanitize_line(md_file: Path, line: str) -> tuple[str, int]:
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        # Skip a link that sits inside an inline-code span.
        if line[: match.start()].count("`") % 2 == 1:
            return match.group(0)
        text, target = match.group(2), match.group(3)
        if _resolves(md_file, target):
            return match.group(0)
        changed += 1
        return text  # drop the link (and any leading `!`), keep the text

    return LINK.sub(replace, line), changed


def sanitize_file(md_file: Path) -> int:
    lines = md_file.read_text(encoding="utf-8").splitlines(keepends=True)
    fenced = False
    total = 0
    out: list[str] = []
    for line in lines:
        if FENCE.match(line):
            fenced = not fenced
            out.append(line)
            continue
        if fenced:
            out.append(line)
            continue
        newline, changed = _sanitize_line(md_file, line)
        total += changed
        out.append(newline)
    if total:
        md_file.write_text("".join(out), encoding="utf-8")
    return total


def main(root: Path) -> int:
    total = 0
    files = 0
    for md_file in sorted(root.rglob("*.md")):
        changed = sanitize_file(md_file)
        if changed:
            files += 1
            total += changed
    print(f"sanitized {total} broken relative link(s) across {files} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
