import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from adversarial_cognition.public_loaders import (
    BEAM_10M_SOURCE,
    BEAM_SOURCE,
    LONGMEMEVAL_SOURCE,
    LOCOMO_SOURCE,
    load_locomo,
    load_longmemeval,
    normalize_beam_row,
)


class AdapterTests(unittest.TestCase):
    def test_beam_dataset_pins_are_exact_even_before_optional_parquet_loading(self) -> None:
        BEAM_SOURCE.validate()
        BEAM_10M_SOURCE.validate()

    def test_pins_are_exact_and_locomo_evidence_is_normalized(self) -> None:
        LOCOMO_SOURCE.validate()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locomo.json"
            path.write_text(
                json.dumps([{"qa": [{"question": "Where?", "evidence": ["D1"]}]}]),
                encoding="utf-8",
            )
            cases = load_locomo(path, date(2026, 1, 1))
        self.assertEqual(cases[0].expected_ids, ("D1",))
        self.assertEqual(cases[0].as_of, date(2026, 1, 1))

    def test_longmemeval_preserves_temporal_and_abstention_labels(self) -> None:
        LONGMEMEVAL_SOURCE.validate()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "longmemeval.json"
            path.write_text(
                json.dumps([
                    {
                        "question_id": "q_abs",
                        "question": "Unknown?",
                        "question_date": "2025-04-03T10:00:00",
                        "answer_session_ids": [],
                    }
                ]),
                encoding="utf-8",
            )
            cases = load_longmemeval(path)
        self.assertTrue(cases[0].abstain)
        self.assertEqual(cases[0].as_of, date(2025, 4, 3))

    def test_beam_normalizer_keeps_only_bounded_question_targets(self) -> None:
        cases = normalize_beam_row(
            {
                "conversation_id": "beam-1",
                "probing_questions": repr(
                    {
                        "information_extraction": [{"question": "Which tool?"}],
                        "abstention": [{"question": "Unknown?"}],
                    }
                ),
            }
        )
        self.assertEqual(cases[0].expected_ids, ("beam-1",))
        self.assertTrue(cases[1].abstain)


if __name__ == "__main__":
    unittest.main()
