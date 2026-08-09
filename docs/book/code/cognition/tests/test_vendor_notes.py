"""Vendor-notes contract: every committed note validates; the gate works."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "check_vendor_notes", ROOT / "scripts" / "check_vendor_notes.py"
)
cvn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cvn)


class VendorNotesTest(unittest.TestCase):
    def test_all_committed_notes_validate(self) -> None:
        notes = [
            p for p in sorted((ROOT / "vendor-notes").glob("*.md"))
            if p.name not in cvn.SKIP
        ]
        for path in notes:
            self.assertEqual(cvn.check_note(path), [], path.name)

    def test_template_is_intentionally_invalid_as_a_note(self) -> None:
        # The template must never validate as-is: SYSTEM_ID is not a system,
        # so an unedited copy fails CI instead of silently publishing.
        fields, _ = cvn.parse_frontmatter(
            (ROOT / "vendor-notes" / "TEMPLATE.md").read_text(encoding="utf-8")
        )
        self.assertNotIn(fields["system"], cvn.KNOWN_SYSTEMS)

    def test_word_cap_enforced(self) -> None:
        note = "---\n" + "\n".join([
            'system: mem0', 'benchmark: MARCIANA-ADVERSARIAL',
            'versions: [v2]', 'subject: "s"', 'author: "a"', 'role: "r"',
            'contact: "c"', 'details: "https://example.com/doc"',
            'verified: false', 'date: 2026-08-08',
        ]) + "\n---\n\n" + ("word " * 150)
        path = ROOT / "vendor-notes" / "mem0.md"
        path.write_text(note, encoding="utf-8")
        try:
            problems = cvn.check_note(path)
        finally:
            path.unlink()
        self.assertTrue(any("cap is 100" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
