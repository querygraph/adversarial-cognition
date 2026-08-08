import tempfile
import unittest
from pathlib import Path

from adversarial_cognition.corpus import SourcePin, load_cases


PIN = SourcePin("local-smoke", "https://example.invalid/fixture", "a" * 40, "normalized-v1")


class CorpusTests(unittest.TestCase):
    def test_loader_requires_exact_pin_and_rejects_duplicate_cases(self) -> None:
        with self.assertRaises(ValueError):
            SourcePin(PIN.name, PIN.url, "unversioned", PIN.schema).validate()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text(
                '{"case_id":"one","query":"coffee","as_of":"2026-01-01","expected_ids":[]}'
                '\n{"case_id":"one","query":"coffee","as_of":"2026-01-01","expected_ids":[]}',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_cases(path, PIN)

    def test_loader_rejects_oversized_queries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            oversized = "q" * 16_385
            path.write_text(
                '{"case_id":"one","query":"' + oversized
                + '","as_of":"2026-01-01","expected_ids":[]}\n',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_cases(path, PIN)

    def test_loader_normalizes_a_bounded_case(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text(
                '{"case_id":"one","query":"coffee","as_of":"2026-01-01",'
                '"expected_ids":["price"],"abstain":false}\n',
                encoding="utf-8",
            )
            cases = load_cases(path, PIN)
        self.assertEqual(cases[0].expected_ids, ("price",))


if __name__ == "__main__":
    unittest.main()
