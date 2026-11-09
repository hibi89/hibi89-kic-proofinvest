"""KUODRA optional sklearn regression and release-lag negative controls."""
import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
import importlib.util
import unittest
from proofinvest.kuodra_unified_core import normalize_local_csv
from proofinvest.kuodra_time_ml import evaluate_lagged_regression


def dataset(*, future_features=False, multi_issuer=False):
    f=StringIO(newline="");w=csv.writer(f,lineterminator="\n")
    w.writerow(("entity_id","metric_id","observation_at","available_at","value","unit"))
    for i in range(100):
        day=datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(days=i)
        timestamp=day.strftime("%Y-%m-%dT%H:%M:%SZ")
        future=(day+timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for entity in (("issuerA","issuerB") if multi_issuer else ("issuerA",)):
            w.writerow((entity,"indicator",timestamp,future if future_features else timestamp,str(i),"count"))
            w.writerow((entity,"nextRevenue",timestamp,timestamp,str(i*3+5),"usd"))
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

    def test_future_only_feature_blocks_training(self):
        result=evaluate_lagged_regression(dataset(future_features=True),target_metric="nextRevenue",
            feature_metrics=("indicator",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(result["status"],"NO_TRAIN")

    def test_multi_issuer_fails_closed(self):
        result=evaluate_lagged_regression(dataset(multi_issuer=True),target_metric="nextRevenue",
            feature_metrics=("indicator",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(result["reason"],"MULTI_ISSUER_GROUP_HOLDOUT_NOT_IMPLEMENTED")

if __name__=="__main__": unittest.main()