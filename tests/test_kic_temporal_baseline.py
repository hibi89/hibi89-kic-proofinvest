"""Conditional AutoML baseline: strict point-in-time and training-label gates."""
from __future__ import annotations

import copy
import unittest

from proofinvest.temporal_baseline import (
    evaluate_historical_baseline, synthetic_temporal_rows,
)

AS_OF = "2025-01-01T00:00:00Z"
_UNSET = object()  # Distinguish omitted rows from explicitly malformed None.


class KicConditionalBaselineTests(unittest.TestCase):
    def setUp(self):
        self.rows = synthetic_temporal_rows()

    def check_block(self, code, *, rows=_UNSET, as_of=AS_OF):
        received = evaluate_historical_baseline(
            self.rows if rows is _UNSET else rows, evaluation_as_of=as_of
        )
        self.assertEqual(received["status"], "NO_TRAIN")
        self.assertEqual(received["reason_code"], code)
        self.assertIsNone(received["metrics"])
        self.assertFalse(received["model_trained"])
        self.assertFalse(received["guard_input_eligible"])
        return received

    def test_synthetic_only_baseline_is_held_out_without_model_fit(self):
        source = copy.deepcopy(self.rows)
        result = evaluate_historical_baseline(self.rows, evaluation_as_of=AS_OF)
        self.assertEqual(result["schema"], "proofinvest.temporal-baseline.v1")
        self.assertEqual(result["status"], "BASELINE_ONLY")
        self.assertEqual((result["train_n"], result["test_n"]), (32, 8))
        self.assertLess(result["train_end"], result["test_start"])
        self.assertLess(result["test_end"], result["as_of"])
        self.assertEqual(result["purged_train_n"], 0)
        self.assertEqual(result["baseline"], "TRAIN_ONLY_MEAN_CONSTANT")
        self.assertTrue(result["baseline_evaluated"])
        self.assertFalse(result["model_trained"])
        self.assertFalse(result["external_source_authenticated"])
        self.assertFalse(result["guard_input_eligible"])
        self.assertFalse(result["investment_recommendation"])
        self.assertFalse(result["trade_executed"])
        self.assertFalse(result["live_api_called"])
        self.assertEqual(self.rows, source)
        self.assertEqual(result, evaluate_historical_baseline(
            self.rows, evaluation_as_of=AS_OF))

    def test_heldout_values_never_change_train_mean(self):
        original = evaluate_historical_baseline(self.rows, evaluation_as_of=AS_OF)
        rows = copy.deepcopy(self.rows)
        rows[-1]["target_value"] = "90000"
        changed = evaluate_historical_baseline(rows, evaluation_as_of=AS_OF)
        self.assertEqual(changed["status"], "BASELINE_ONLY")
        self.assertEqual(changed["metrics"]["train_mean"],
                         original["metrics"]["train_mean"])
        self.assertNotEqual(changed["metrics"]["heldout_mae"],
                            original["metrics"]["heldout_mae"])

    def test_missing_rows_or_insufficient_history_never_train(self):
        for x in ([], [1], None, self.rows[:29], {}):
            with self.subTest(x=str(type(x))):
                self.check_block("INSUFFICIENT_INDEPENDENT_OBSERVATIONS", rows=x)

    def test_actual_or_unspecified_source_disallowed(self):
        for kind in ("SEC_HTTPS_RESPONSE", "MANUAL", None):
            with self.subTest(kind=kind):
                rows = copy.deepcopy(self.rows)
                rows[0]["source_kind"] = kind
                self.check_block("SOURCE_PROVENANCE_NOT_ELIGIBLE", rows=rows)

    def test_rights_unclear_never_train(self):
        rows = copy.deepcopy(self.rows)
        rows[1]["rights_status"] = "UNKNOWN"
        self.check_block("SOURCE_RIGHTS_NOT_CLEARED", rows=rows)

    def test_future_feature_release_vintage_or_first_seen_fails(self):
        for key in ("released_at", "vintage_at", "first_seen_at"):
            with self.subTest(key=key):
                rows = copy.deepcopy(self.rows)
                rows[2]["features"]["lagged_context"][key] = (
                    "2031-01-01T00:00:00Z")
                self.check_block("FUTURE_FEATURE_OR_REVISION_LEAKAGE", rows=rows)

    def test_undocumented_or_backdated_labels_fail(self):
        rows = copy.deepcopy(self.rows)
        rows[-1]["target_available_at"] = "2031-01-01T00:00:00Z"
        self.check_block("FUTURE_OR_BACKFILLED_TARGET", rows=rows)
        rows = copy.deepcopy(self.rows)
        rows[0]["target_first_seen_at"] = "2019-01-01T00:00:00Z"
        self.check_block("FUTURE_OR_BACKFILLED_TARGET", rows=rows)

    def test_holdout_label_not_yet_observed_is_blocked(self):
        self.check_block("FUTURE_OR_BACKFILLED_TARGET",
                         as_of="2022-01-01T00:00:00Z")

    def test_malformed_or_not_utc_timestamp_rejected(self):
        for value in ("2025-01-01", "2025-01-01T00:00:00+09:00",
                      "2025-02-30T00:00:00Z", ""):
            with self.subTest(value=value):
                self.check_block("INVALID_EVALUATION_CLOCK", as_of=value)

    def test_future_prediction_feature_and_duplicate_period(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["prediction_at"] = "2025-12-01T00:00:00Z"
        self.check_block("FUTURE_OR_BACKFILLED_TARGET", rows=rows)
        rows = copy.deepcopy(self.rows)
        rows[1]["prediction_at"] = rows[0]["prediction_at"]
        self.check_block("DUPLICATED_ISSUER_PERIOD", rows=rows)

    def test_feature_name_guards_target_leakage(self):
        for name in ("future_target", "label_return", "outcome_price"):
            with self.subTest(name=name):
                rows = copy.deepcopy(self.rows)
                rows[1]["features"] = {name: rows[1]["features"]["lagged_context"]}
                self.check_block("FEATURE_OR_TARGET_LEAKAGE", rows=rows)

    def test_nonfinite_float_string_or_invalid_amount_rejected(self):
        for value in ("NaN", "Infinity", "1e9", "1,000", "999999999999999999", 1.5):
            with self.subTest(value=value):
                rows = copy.deepcopy(self.rows)
                rows[0]["target_value"] = value
                self.check_block("NUMERIC_VALUE_INVALID", rows=rows)

    def test_missing_feature_provenance_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows[3]["features"]["lagged_context"]["source_ref"] = ""
        self.check_block("FEATURE_LINEAGE_MISSING", rows=rows)

    def test_deduplicate_target_source_and_overlapping_horizons(self):
        rows = copy.deepcopy(self.rows)
        rows[1]["target_source_ref"] = rows[0]["target_source_ref"]
        self.check_block("DUPLICATED_TARGET_SOURCE", rows=rows)
        rows = copy.deepcopy(self.rows)
        rows[1]["prediction_at"] = rows[0]["prediction_at"][:-9] + "01T10:00:00Z"
        # Different clock within prior target horizon (first period ends 16th).
        rows[1]["prediction_at"] = "2020-01-02T00:00:00Z"
        # Feature must be released before the modified prediction time.
        rows[1]["features"]["lagged_context"]["released_at"] = "2019-12-31T00:00:00Z"
        rows[1]["features"]["lagged_context"]["vintage_at"] = "2019-12-31T00:00:00Z"
        rows[1]["features"]["lagged_context"]["first_seen_at"] = "2019-12-31T00:00:00Z"
        self.check_block("OVERLAPPING_LABEL_HORIZONS", rows=rows)

    def test_train_label_late_publication_is_purged(self):
        rows = copy.deepcopy(self.rows)
        first_test_date = rows[32]["prediction_at"]
        rows[31]["target_first_seen_at"] = first_test_date
        result = evaluate_historical_baseline(rows, evaluation_as_of=AS_OF)
        self.assertEqual(result["status"], "BASELINE_ONLY")
        self.assertEqual(result["purged_train_n"], 1)
        self.assertEqual((result["train_n"], result["test_n"]), (31, 8))

    def test_too_many_purged_training_labels_yields_no_train(self):
        rows = copy.deepcopy(self.rows)
        cutoff = rows[32]["prediction_at"]
        for item in rows[8:32]:
            item["target_first_seen_at"] = cutoff
        self.check_block("INSUFFICIENT_LEAK_FREE_TRAIN_HOLDOUT", rows=rows)

    def test_panel_same_clock_never_split_between_train_test(self):
        rows = copy.deepcopy(self.rows)
        for i, item in enumerate(self.rows):
            second = copy.deepcopy(item)
            second["issuer_id"] = "SYNTHETIC_SECOND"
            second["target_source_ref"] = f"self-authored:second-target:{i}"
            rows.append(second)
        result = evaluate_historical_baseline(rows, evaluation_as_of=AS_OF)
        self.assertEqual(result["status"], "BASELINE_ONLY")
        self.assertEqual((result["train_n"], result["test_n"]), (64, 16))
        self.assertEqual(result["train_end"], self.rows[31]["prediction_at"])
        self.assertEqual(result["test_start"], self.rows[32]["prediction_at"])

    def test_missing_source_or_invalid_features_fails(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["features"] = {}
        self.check_block("FEATURE_LINEAGE_MISSING", rows=rows)
        rows = copy.deepcopy(self.rows)
        rows[0]["target_source_ref"] = ""
        self.check_block("TARGET_SOURCE_NOT_PINNED", rows=rows)


if __name__ == "__main__":
    unittest.main()
