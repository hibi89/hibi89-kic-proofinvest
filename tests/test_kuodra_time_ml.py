"""KUODRA optional sklearn regression and release-lag negative controls."""
import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
import importlib.util
import unittest
from proofinvest.kuodra_unified_core import normalize_local_csv
from proofinvest.kuodra_time_ml import evaluate_lagged_regression


def dataset(*, future_features=False, multi_issuer=False, cadence="daily",
            unrelated_intraday=False, unreleased_midday_targets=False):
    f=StringIO(newline="");w=csv.writer(f,lineterminator="\n")
    w.writerow(("entity_id","metric_id","observation_at","available_at","value","unit"))
    for i in range(100):
        elapsed=(i if cadence=="daily" else i+2*(i//4)
                 if cadence=="mixed" else 30*i+(i%2)
                 if cadence=="month" else 370*i
                 if cadence=="yearly" else None)
        if elapsed is None:
            raise ValueError("SYNTHETIC_CADENCE_INVALID")
        day=datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(days=elapsed)
        timestamp=day.strftime("%Y-%m-%dT%H:%M:%SZ")
        future=(day+timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for entity in (("issuerA","issuerB") if multi_issuer else ("issuerA",)):
            w.writerow((entity,"indicator",timestamp,future if future_features else timestamp,str(i),"count"))
            w.writerow((entity,"nextRevenue",timestamp,timestamp,str(i*3+5),"usd"))
            if unrelated_intraday and i<99:
                midday=(day+timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
                w.writerow((entity,"unrelatedSignal",midday,midday,"1","count"))
            if unreleased_midday_targets and 20 <= i < 80:
                # A fictional future-released target dated between normal
                # observations is invisible at the 2026 review cut-off.
                midday=(day+timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
                w.writerow((entity,"nextRevenue",midday,
                            "2027-01-01T00:00:00Z",str(i*3+6),"usd"))
    return normalize_local_csv(f.getvalue().encode(),dataset_id="mlSynthetic",source_id="fixture",
        access_level="PRIVATE",consent=True)


class MLAdapterTest(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("sklearn"),"sklearn optional offline package")
    def test_real_holdout_runs_locally(self):
        result=evaluate_lagged_regression(dataset(),target_metric="nextRevenue",
            feature_metrics=("indicator",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(result["status"],"EXPLORATORY_HOLDOUT_MEASURED")
        self.assertEqual(result["selected_by_cv"],"ridge_scaled")
        self.assertTrue(result["holdout_improvement_pct"]>0)
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual(result["guard"],"HOLD")
        self.assertFalse(result["production_ready"])

    @unittest.skipUnless(importlib.util.find_spec("sklearn"),"sklearn optional")
    def test_unrelated_intraday_metric_does_not_change_target_predictions(self):
        options=dict(target_metric="nextRevenue",feature_metrics=("indicator",),
                     as_of="2026-01-01T00:00:00Z")
        original=evaluate_lagged_regression(dataset(),**options)
        with_noise=evaluate_lagged_regression(dataset(unrelated_intraday=True),**options)
        self.assertEqual(original["status"],"EXPLORATORY_HOLDOUT_MEASURED")
        self.assertNotEqual(original["source_sha256"],with_noise["source_sha256"])
        for key in original:
            if key != "source_sha256":
                self.assertEqual(with_noise[key],original[key],key)
        self.assertEqual(with_noise["guard"],"HOLD")

    @unittest.skipUnless(importlib.util.find_spec("sklearn"),"sklearn optional")
    def test_unreleased_target_observations_cannot_erase_asof_train_samples(self):
        # The historical review must ignore a later-released value dated
        # between 60 otherwise valid daily target observations. Previously
        # these target rows broke the NEXT_OBSERVATION calendar and returned
        # NO_TRAIN despite adding no information available at this as-of.
        options=dict(target_metric="nextRevenue",feature_metrics=("indicator",),
                     as_of="2026-01-01T00:00:00Z")
        baseline=evaluate_lagged_regression(dataset(),**options)
        expanded=evaluate_lagged_regression(
            dataset(unreleased_midday_targets=True),**options)
        self.assertEqual(baseline["status"],"EXPLORATORY_HOLDOUT_MEASURED")
        self.assertEqual(expanded["status"],"EXPLORATORY_HOLDOUT_MEASURED")
        self.assertNotEqual(baseline["source_sha256"],expanded["source_sha256"])
        for key in baseline:
            if key!="source_sha256":
                self.assertEqual(expanded[key],baseline[key],key)
        self.assertEqual(expanded["guard"],"HOLD")
        self.assertIsNone(expanded["calibrated_probability"])

    def test_mixed_interval_single_issuer_next_observation_denied(self):
        r=evaluate_lagged_regression(dataset(cadence="mixed"),
            target_metric="nextRevenue",feature_metrics=("indicator",),
            as_of="2026-01-01T00:00:00Z")
        self.assertEqual(r["status"],"NO_TRAIN")
        self.assertEqual(r["reason"],"INCONSISTENT_NEXT_OBSERVATION_HORIZON")
        self.assertEqual(r["guard"],"HOLD")
        self.assertNotIn("holdout_selected_mae",r)

    @unittest.skipUnless(importlib.util.find_spec("sklearn"),"sklearn optional")
    def test_month_like_horizon_allowed_but_only_exploratory(self):
        r=evaluate_lagged_regression(dataset(cadence="month"),
            target_metric="nextRevenue",feature_metrics=("indicator",),
            as_of="2035-01-01T00:00:00Z")
        self.assertEqual(r["status"],"EXPLORATORY_HOLDOUT_MEASURED")
        self.assertEqual(r["observed_horizon_min_days"],29.0)
        self.assertEqual(r["observed_horizon_max_days"],31.0)
        self.assertFalse(r["production_ready"])
        self.assertEqual(r["guard"],"HOLD")

    def test_above_one_year_interval_denied_before_model_fit(self):
        r=evaluate_lagged_regression(dataset(cadence="yearly"),
            target_metric="nextRevenue",feature_metrics=("indicator",),
            as_of="2200-01-01T00:00:00Z")
        self.assertEqual(r["status"],"NO_TRAIN")
        self.assertEqual(r["reason"],"INCONSISTENT_NEXT_OBSERVATION_HORIZON")
        self.assertNotIn("cv_mae",r)

    def test_future_only_feature_blocks_training(self):
        result=evaluate_lagged_regression(dataset(future_features=True),target_metric="nextRevenue",
            feature_metrics=("indicator",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(result["status"],"NO_TRAIN")

    def test_multi_issuer_fails_closed(self):
        result=evaluate_lagged_regression(dataset(multi_issuer=True),target_metric="nextRevenue",
            feature_metrics=("indicator",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(result["reason"],"MULTI_ISSUER_GROUP_HOLDOUT_NOT_IMPLEMENTED")

if __name__=="__main__": unittest.main()