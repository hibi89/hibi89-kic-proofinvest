"""No network, no training: KUODRA ML explanation contract tests."""
import copy
import json
import unittest
from unittest.mock import patch

from proofinvest.ml_explainability import (
    MAX_ML_REPORT_BYTES, explain_ml_evaluation, parse_ml_evaluation_json,
)


def example():
    return {
        "schema": "kuodra.ml-evaluation.v1", "status": "EVALUATED",
        "issuer_cik": "0000320193", "as_of": "2026-10-31",
        "model_name": "Ridge", "target": "historical_revenue_change",
        "evaluation": {
            "split": "WALK_FORWARD", "train_end": "2023-12-31",
            "test_start": "2024-01-01", "test_end": "2025-12-31",
            "train_rows": 80, "test_rows": 16, "metric": "MAE",
            "baseline_value": "5.00", "model_value": "4.00",
        },
        "sources": [{"id": "sec", "url": "https://www.sec.gov/Archives/edgar/data/",
                     "published_at": "2025-12-31", "sha256": "a" * 64}],
        "features": [{"name": "revenue_growth", "method": "PERMUTATION_IMPORTANCE",
                      "importance": "0.20", "source_ids": ["sec"]}],
    }


class MlExplanationTests(unittest.TestCase):
    def test_model_report_not_misrepresented_as_verified(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO HTTP")) as network:
            result = explain_ml_evaluation(example(), expected_issuer_cik="0000320193",
                                           analysis_as_of="2026-10-31")
        network.assert_not_called()
        self.assertEqual(result["status"], "REPORTED_UNVERIFIED")
        self.assertTrue(result["metric_comparison"]["reported_improvement"])
        self.assertFalse(result["model_verified"])
        self.assertFalse(result["ai_generated"])
        self.assertFalse(result["trade_signal"])
        self.assertEqual(result["factors"][0]["source_ids"], ["sec"])
        self.assertFalse(result["sources"][0]["authenticated"])

    def test_no_gain_is_explained_without_fabricated_confidence(self):
        obj = example()
        obj["evaluation"]["model_value"] = "6.0"
        result = explain_ml_evaluation(obj)
        self.assertFalse(result["metric_comparison"]["reported_improvement"])
        self.assertIn("개선이 확인되지", result["summary"])
        self.assertNotIn("confidence", result)

    def test_no_train_fails_closed_without_sources(self):
        obj = {"schema": "kuodra.ml-evaluation.v1", "status": "NO_TRAIN",
               "issuer_cik": "0000320193", "as_of": "2026-10-31",
               "reason_code": "INSUFFICIENT_GROUPS"}
        result = explain_ml_evaluation(obj)
        self.assertEqual(result["status"], "NO_TRAIN")
        self.assertEqual(result["factors"], [])
        self.assertIsNone(result["metric_comparison"])
        for key in ("features", "model_name", "sources"):
            bad = obj | {key: []}
            with self.assertRaises(ValueError):
                explain_ml_evaluation(bad)

    def test_future_data_wrong_issuer_and_non_walkforward_rejected(self):
        for change in (
            {"as_of": "2024-01-01"},
            {"issuer_cik": "0000000000"},
            {"evaluation": example()["evaluation"] | {"split": "RANDOM"}},
            {"evaluation": example()["evaluation"] | {"test_start": "2023-01-01"}},
            {"sources": [example()["sources"][0] | {"published_at": "2026-11-01"}]},
            {"features": [example()["features"][0] | {"source_ids": ["missing"]}]},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                explain_ml_evaluation(example() | change)
        with self.assertRaisesRegex(ValueError, "ML_ISSUER_MISMATCH"):
            explain_ml_evaluation(example(), expected_issuer_cik="0000000001")
        with self.assertRaisesRegex(ValueError, "ML_AS_OF_MISMATCH"):
            explain_ml_evaluation(example(), analysis_as_of="2026-10-30")

    def test_no_sources_duplicates_and_unsafe_urls(self):
        obj = example()
        for url in ("http://example.org/a", "https://localhost/a", "https://x.com/a?key=secret",
                    "https://name:pass@x.com/a", "https://x.com:99999/a"):
            bad = copy.deepcopy(obj)
            bad["sources"][0]["url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                explain_ml_evaluation(bad)
        bad = copy.deepcopy(obj)
        bad["sources"].append(bad["sources"][0])
        with self.assertRaises(ValueError):
            explain_ml_evaluation(bad)

    def test_strict_json_bound_duplicates_and_nan(self):
        parsed = parse_ml_evaluation_json(json.dumps(example()).encode())
        self.assertEqual(explain_ml_evaluation(parsed)["status"], "REPORTED_UNVERIFIED")
        for raw in (b'{"schema":"x","schema":"y"}', b'{"metric":NaN}',
                    b"{" + b" " * MAX_ML_REPORT_BYTES + b"}", b"\xff"):
            with self.subTest(raw=raw[:24]), self.assertRaises(ValueError):
                parse_ml_evaluation_json(raw)


if __name__ == "__main__":
    unittest.main()
