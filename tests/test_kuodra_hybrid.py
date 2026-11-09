"""Synthetic private/public hybrid join: ACL, release-time, no-egress and ML."""
import csv
from datetime import datetime, timezone, timedelta
from io import StringIO
import socket
import unittest
from unittest.mock import patch

from proofinvest.kuodra_hybrid import analyze_local_hybrid
from proofinvest.kuodra_alias_hybrid import _prepare_owner_alias_view
from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal

OWNER = VerifiedPrincipal("owner1", "fund1", ("owner",), True)
ANALYST = VerifiedPrincipal("analyst1", "fund1", ("analyst",), True)
VIEWER = VerifiedPrincipal("viewer1", "fund1", ("viewer",), True)
OUTSIDER = VerifiedPrincipal("owner2", "fund2", ("owner",), True)
UNVERIFIED = VerifiedPrincipal("owner1", "fund1", ("owner",), False)


def csv_rows(*, issuer_count=1, days=80, private=False,
             delay_feature_days=0, offset_days=0):
    f = StringIO(newline="")
    w = csv.writer(f, lineterminator="\n")
    w.writerow(("entity_id", "metric_id", "observation_at", "available_at", "value", "unit"))
    for j in range(days):
        day = datetime(2025, 1, 1, tzinfo=timezone.utc)+timedelta(days=j+offset_days)
        obs = day.strftime("%Y-%m-%dT%H:%M:%SZ")
        ready = (day+timedelta(days=delay_feature_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for issuer in range(issuer_count):
            if private:
                metric, value, unit = "outcome", str(4*j+issuer+10), "usd"
                av = obs
            else:
                metric, value, unit = "factor", str(j+issuer+1), "count"
                av = ready
            w.writerow((f"issuer{issuer}", metric, obs, av, value, unit))
    return f.getvalue().encode("utf-8")


def gateway(*, count=1, days=80, offset=0, late=0):
    g = OwnerLocalGateway("fund1")
    g.ingest_csv(OWNER, raw=csv_rows(issuer_count=count, days=days,
                 delay_feature_days=late, offset_days=offset),
                 dataset_id="publicA", source_id="publicFixture",
                 access_level="PUBLIC")
    g.ingest_csv(OWNER, raw=csv_rows(issuer_count=count, days=days, private=True),
                 dataset_id="privateA", source_id="internalFixture",
                 access_level="PRIVATE")
    approved, _ = _prepare_owner_alias_view(
        g, OWNER, public_dataset_id="publicA", private_dataset_id="privateA",
        public_sha256=g._datasets["publicA"]["source_sha256"],
        private_sha256=g._datasets["privateA"]["source_sha256"],
        aliases={r["entity_id"]:r["entity_id"]
                 for r in g._datasets["publicA"]["records"]},
        as_of="2026-01-01T00:00:00Z")
    return approved


def analyze(g, principal=ANALYST, **kwargs):
    return analyze_local_hybrid(g, principal,
        public_dataset_id="publicA", private_dataset_id="privateA",
        as_of="2026-01-01T00:00:00Z", **kwargs)


class HybridTest(unittest.TestCase):
    def test_cross_source_statistics_are_private_and_synthetic(self):
        g=gateway(count=45,days=1)
        r=analyze(g,mode="cross_section",metrics=("public.factor","private.outcome"),
                  observation_at="2025-01-01T00:00:00Z")
        self.assertEqual(r["joined_entity_times"],45)
        self.assertEqual(r["analysis"]["pairs_evaluated"],1)
        self.assertAlmostEqual(r["analysis"]["insights"][0]["pearson_r"],1)
        self.assertEqual(r["analysis"]["guard"],"HOLD")
        self.assertEqual(r["access_level"],"PRIVATE")
        self.assertFalse(r["public_export_allowed"])
        self.assertFalse(r["host_egress_policy_verified"])
        self.assertNotIn("records",str(r))

    def test_model_cv_holdout_selects_offline_challenger(self):
        g=gateway(days=90)
        r=analyze(g,mode="predictive",target_metric="private.outcome",
                  feature_metrics=("public.factor",))
        self.assertEqual(r["analysis"]["status"],"EXPLORATORY_HOLDOUT_MEASURED")
        self.assertEqual(r["analysis"]["selected_by_cv"],"ridge_scaled")
        self.assertEqual(r["analysis"]["guard"],"HOLD")
        self.assertFalse(r["analysis"]["production_ready"])

    def test_raw_equal_issuer_ids_cannot_join_without_owner_mapping(self):
        original=OwnerLocalGateway("fund1")
        original.ingest_csv(OWNER,raw=csv_rows(issuer_count=10),
            dataset_id="publicA",source_id="publicFixture",access_level="PUBLIC")
        original.ingest_csv(OWNER,raw=csv_rows(issuer_count=10,private=True),
            dataset_id="privateA",source_id="internalFixture",access_level="PRIVATE")
        with self.assertRaisesRegex(PermissionError,"HYBRID_OWNER_MAPPING_REQUIRED"):
            analyze(original,mode="predictive",target_metric="private.outcome",
                    feature_metrics=("public.factor",))

    def test_approved_view_bound_to_asof_and_snapshot(self):
        view=gateway(count=10)
        with self.assertRaisesRegex(PermissionError,"HYBRID_OWNER_MAPPING_REQUIRED"):
            analyze_local_hybrid(view,ANALYST,public_dataset_id="publicA",
                private_dataset_id="privateA",as_of="2027-01-01T00:00:00Z",
                mode="predictive",target_metric="private.outcome",
                feature_metrics=("public.factor",))
        view._datasets["publicA"]["records"][0]["value"]="1234"
        with self.assertRaisesRegex(ValueError,"HYBRID_APPROVED_SNAPSHOT_CHANGED"):
            analyze(view,mode="predictive",target_metric="private.outcome",
                    feature_metrics=("public.factor",))

    def test_unauthorized_reads_denied_before_join(self):
        g=gateway()
        for principal in (VIEWER,OUTSIDER,UNVERIFIED):
            with self.assertRaisesRegex(PermissionError,"GATEWAY_ACCESS_DENIED"):
                analyze(g,principal,mode="predictive",target_metric="private.outcome",
                        feature_metrics=("public.factor",))

    def test_wrong_public_private_labels_rejected(self):
        g=gateway()
        g._datasets["publicA"]["access_level"]="PRIVATE"
        with self.assertRaisesRegex(ValueError,"HYBRID_APPROVED_SNAPSHOT_CHANGED"):
            analyze(g,mode="predictive",target_metric="private.outcome",
                    feature_metrics=("public.factor",))

    def test_source_lineage_tampering_rejected(self):
        g=gateway()
        g._datasets["privateA"]["records"][0]["source_id"]="other"
        with self.assertRaisesRegex(ValueError,"HYBRID_APPROVED_SNAPSHOT_CHANGED"):
            analyze(g,mode="predictive",target_metric="private.outcome",
                    feature_metrics=("public.factor",))

    def test_future_only_public_feature_cannot_train(self):
        g=gateway(days=80,late=2)
        r=analyze(g,mode="predictive",target_metric="private.outcome",
                  feature_metrics=("public.factor",))
        self.assertEqual(r["analysis"]["status"],"NO_TRAIN")

    def test_cross_entity_time_no_match_fail_closed(self):
        g=gateway(days=10,offset=400)
        r=analyze(g,mode="cross_section",metrics=("public.factor","private.outcome"),
                  observation_at="2025-01-01T00:00:00Z")
        self.assertEqual(r["joined_entity_times"],0)
        self.assertEqual(r["analysis"]["status"],"NO_ANALYSIS")

    def test_insufficient_observations_withhold_stats(self):
        g=gateway(count=9,days=1)
        r=analyze(g,mode="cross_section",metrics=("public.factor","private.outcome"),
                  observation_at="2025-01-01T00:00:00Z")
        self.assertEqual(r["analysis"]["status"],"INSUFFICIENT_EVIDENCE")

    def test_multi_issuer_ml_denied(self):
        g=gateway(count=2)
        r=analyze(g,mode="predictive",target_metric="private.outcome",
                  feature_metrics=("public.factor",))
        self.assertEqual(r["analysis"]["reason"],
                         "MULTI_ISSUER_GROUP_HOLDOUT_NOT_IMPLEMENTED")

    def test_no_network_calls_at_join_or_ml(self):
        g=gateway()
        with patch.object(socket.socket,"connect",side_effect=AssertionError("EGRESS")) as conn:
            r=analyze(g,mode="predictive",target_metric="private.outcome",
                      feature_metrics=("public.factor",))
            self.assertFalse(r["public_export_allowed"])
            conn.assert_not_called()

    def test_metric_namespaces_required(self):
        g=gateway()
        for names in (("public.factor","public.other"), ("factor","private.outcome"),
                      ("public.factor","private.outcome","private.outcome")):
            with self.assertRaisesRegex(ValueError,"HYBRID_METRIC_NAMESPACE_INVALID"):
                analyze(g,mode="cross_section",metrics=names,
                        observation_at="2025-01-01T00:00:00Z")

    def test_data_permission_is_per_dataset(self):
        g=gateway()
        g._allowed_roles["privateA"]=frozenset({"owner"})
        with self.assertRaises(PermissionError):
            analyze(g,mode="predictive",target_metric="private.outcome",
                    feature_metrics=("public.factor",))
        r=analyze(g,OWNER,mode="predictive",target_metric="private.outcome",
                  feature_metrics=("public.factor",))
        self.assertEqual(r["access_level"],"PRIVATE")

    def test_public_and_private_must_be_different_datasets(self):
        g=gateway()
        with self.assertRaises(ValueError):
            analyze_local_hybrid(g,ANALYST,public_dataset_id="publicA",
                private_dataset_id="publicA",as_of="2026-01-01T00:00:00Z",
                mode="predictive",target_metric="private.outcome",
                feature_metrics=("public.factor",))

    def test_report_is_deep_copied_not_reference_to_source(self):
        g=gateway(count=50,days=1)
        a=analyze(g,mode="cross_section",metrics=("public.factor","private.outcome"),
                  observation_at="2025-01-01T00:00:00Z")
        a["analysis"]["insights"][0]["pearson_r"]=-7
        b=analyze(g,mode="cross_section",metrics=("public.factor","private.outcome"),
                  observation_at="2025-01-01T00:00:00Z")
        self.assertNotEqual(b["analysis"]["insights"][0]["pearson_r"],-7)

    def test_unknown_ids_denied_without_existence_leak(self):
        g=gateway()
        with self.assertRaisesRegex(PermissionError,"^GATEWAY_ACCESS_DENIED$"):
            analyze_local_hybrid(g,ANALYST,public_dataset_id="unknown",
                private_dataset_id="privateA",as_of="2026-01-01T00:00:00Z",
                mode="predictive",target_metric="private.outcome",
                feature_metrics=("public.factor",))


if __name__ == "__main__":
    unittest.main()
