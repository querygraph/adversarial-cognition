import unittest

from adversarial_cognition.metrics import CaseResult, percentile, summarize
from adversarial_cognition.metadata import BenchmarkMetadata


class MetricsTests(unittest.TestCase):
    def test_summary_has_accuracy_latency_and_safety_gates(self) -> None:
        rows = [
            CaseResult("ok", ("a",), ("a",), (), 10.0, 4),
            CaseResult("redacted", (), (), ("secret",), 20.0, 0),
        ]
        report = summarize(rows)
        self.assertEqual(report["accuracy"], 1.0)
        self.assertEqual(report["redaction_leaks"], 0)
        self.assertEqual(report["p95_latency_us"], 20.0)
        self.assertEqual(report["p99_latency_us"], 20.0)

    def test_percentile_empty_is_safe(self) -> None:
        self.assertEqual(percentile([], 95), 0.0)

    def test_benchmark_metadata_is_strict_and_serializable(self) -> None:
        metadata = BenchmarkMetadata("model", "local", "none", "none", "profile", "arm64", "rev")
        self.assertEqual(metadata.as_dict()["revision"], "rev")
        with self.assertRaises(ValueError):
            BenchmarkMetadata("", "local", "none", "none", "profile", "arm64", "rev")


if __name__ == "__main__":
    unittest.main()
