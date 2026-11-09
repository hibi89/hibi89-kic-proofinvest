"""Issuer/time heldout synthetic backend acceptance and negative controls."""
import csv
import math
from datetime import datetime, timedelta, timezone
from io import StringIO
import socket
from unittest import TestCase
from unittest.mock import patch

from proofinvest.kuodra_unified_core import normalize_local_csv
from proofinvest.kuodra_alias_hybrid import _prepare_owner_alias_view
from proofinvest.kuodra_group_time_ml import (
    evaluate_issuer_time_holdout, evaluate_owner_local_group,
    evaluate_owner_local_hybrid_group)
from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal

OWNER=VerifiedPrincipal("ownerA","fundA",("owner",),True)
ANALYST=VerifiedPrincipal("analystA","fundA",("analyst",),True)
WRONG=VerifiedPrincipal("analystB","fundB",("analyst",),True)
UNVERIFIED=VerifiedPrincipal("anon","fundA",("analyst",),False)


def rows(*, issuers=10, dates=62, zone="PUBLIC", future_features=False,
         late_labels=False, duplicate_target=False, random_labels=False,
         late_drift=False, cadence="daily"):
    output=StringIO(newline="")
    w=csv.writer(output,lineterminator="\n")
    w.writerow(("entity_id", "metric_id", "observation_at", "available_at", "value", "unit"))
    for j in range(issuers):
        for i in range(dates):
            # Monthly calendar drift (29/31 days) is materially different
            # from a mixed 1/3-day unknown prediction horizon.
            elapsed = (i if cadence=="daily" else
                       30*i+(i%2) if cadence=="month" else
                       i+2*(i//4) if cadence=="mixed" else None)
            if elapsed is None:
                raise ValueError("SYNTHETIC_CADENCE_INVALID")
            t=datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(days=elapsed)
            obs=t.strftime("%Y-%m-%dT%H:%M:%SZ")
            feature_release=(t+timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ") if future_features else obs
            target_release=(t+timedelta(days=80)).strftime("%Y-%m-%dT%H:%M:%SZ") if late_labels else obs
            x=i+j*0.4
            y=(j*33+i*27)%97 if random_labels else (i*3 + j*2 + 4)
            if late_drift and i>=54:
                y += 10000
            w.writerow((f"issuer{j}","feature",obs,feature_release,str(round(x,3)),"count"))
            w.writerow((f"issuer{j}","target",obs,target_release,str(y),"usd"))
            if duplicate_target and j == 0 and i == 0:
                w.writerow((f"issuer{j}","target",obs,target_release,str(y),"usd"))
    return output.getvalue().encode()


def data(**kwargs):
    zone=kwargs.pop("zone","PUBLIC")
    return normalize_local_csv(rows(zone=zone,**kwargs),dataset_id="fixture",
        source_id="synthetic",access_level=zone,consent=zone=="PRIVATE")


class IssuerTimeMLTest(TestCase):
    def test_unseen_issuers_and_later_time_holdout(self):
        result=evaluate_issuer_time_holdout(data(),target_metric="target",
            feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(result["status"],"EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertEqual(result["train_issuer_count"]+result["holdout_issuer_count"],10)
        self.assertEqual(result["split"],"DISJOINT_ISSUER_LATER_TIME_WITH_RELEASE_EMBARGO")
        self.assertGreater(result["train_n"],50)
        self.assertGreater(result["holdout_n"],12)
        self.assertFalse(result["production_ready"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual(result["guard"],"HOLD")
        self.assertNotIn("issuer0",str(result))

    def test_unrelated_intraday_metric_cannot_shift_target_time_split(self):
        baseline=evaluate_issuer_time_holdout(data(), target_metric="target",
            feature_metrics=("feature",), as_of="2026-01-01T00:00:00Z")
        extras=[]
        for issuer in range(10):
            for day in range(61):
                moment=(datetime(2025,1,1,tzinfo=timezone.utc)
                        + timedelta(days=day,hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
                extras.append(f"issuer{issuer},intradayNoise,{moment},{moment},1,count\n")
        source=normalize_local_csv(rows()+''.join(extras).encode(),
            dataset_id="fixture",source_id="synthetic",access_level="PUBLIC")
        actual=evaluate_issuer_time_holdout(source,target_metric="target",
            feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(baseline["status"],"EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertEqual(actual,baseline)
        self.assertEqual(actual["guard"],"HOLD")

    def test_unrelated_companies_without_target_cannot_change_issuer_holdout(self):
        base=evaluate_issuer_time_holdout(data(),target_metric="target",
            feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
        extra=''.join(
            f"noiseIssuer{j},unrelatedSignal,2025-01-01T00:00:00Z,2025-01-01T00:00:00Z,7,count\\n"
            for j in range(35)).replace("\\n","\n").encode()
        combined=normalize_local_csv(rows()+extra,dataset_id="fixture",
            source_id="synthetic",access_level="PUBLIC")
        actual=evaluate_issuer_time_holdout(combined,target_metric="target",
            feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(base["status"],"EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertEqual(actual,base)
        self.assertEqual(actual["issuer_count"],10)

    def test_target_only_issuers_without_features_cannot_shift_holdout(self):
        base=evaluate_issuer_time_holdout(data(),target_metric="target",
            feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
        extras=[]
        for issuer in range(18):
            for day in range(62):
                at=(datetime(2025,1,1,tzinfo=timezone.utc)+
                    timedelta(days=day)).strftime("%Y-%m-%dT%H:%M:%SZ")
                extras.append(f"untrainedIssuer{issuer},target,{at},{at},123,usd\n")
        combined=normalize_local_csv(rows()+''.join(extras).encode(),
            dataset_id="fixture",source_id="synthetic",access_level="PUBLIC")
        actual=evaluate_issuer_time_holdout(combined,target_metric="target",
            feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(actual,base)

    def test_target_only_tail_without_usable_samples_cannot_shift_time_split(self):
        # Missing last-day features make all later target-only rows unusable
        # as prediction origins. Appending them must not alter an old result.
        raw = b"".join(
            line for line in rows().splitlines(keepends=True)
            if b",feature,2025-03-03T00:00:00Z," not in line)
        baseline_data = normalize_local_csv(raw, dataset_id="fixture",
            source_id="synthetic", access_level="PUBLIC")
        tail = []
        for issuer in range(10):
            for day in range(62, 90):
                at = (datetime(2025, 1, 1, tzinfo=timezone.utc) +
                      timedelta(days=day)).strftime("%Y-%m-%dT%H:%M:%SZ")
                tail.append(f"issuer{issuer},target,{at},{at},999,usd\\n")
        expanded_data = normalize_local_csv(raw + "".join(tail).encode(),
            dataset_id="fixture", source_id="synthetic", access_level="PUBLIC")
        kwargs = dict(target_metric="target", feature_metrics=("feature",),
                      as_of="2026-01-01T00:00:00Z")
        baseline = evaluate_issuer_time_holdout(baseline_data, **kwargs)
        self.assertEqual(baseline["status"],
                         "EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertEqual(evaluate_issuer_time_holdout(expanded_data, **kwargs),
                         baseline)

    def test_noise_companies_do_not_satisfy_minimum_trainable_issuer_count(self):
        extra=''.join(
            f"fillerIssuer{i},noise,2025-01-01T00:00:00Z,2025-01-01T00:00:00Z,3,count\n"
            for i in range(20)).encode()
        combined=normalize_local_csv(rows(issuers=7)+extra,
            dataset_id="fixture",source_id="synthetic",access_level="PUBLIC")
        result=evaluate_issuer_time_holdout(combined,target_metric="target",
            feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(result["status"],"NO_TRAIN")
        self.assertEqual(result["reason"],"INSUFFICIENT_DISTINCT_ISSUERS")
        self.assertEqual(result["guard"],"HOLD")

    def test_future_dates_cannot_shift_historical_holdout_boundary(self):
        # Historical evaluation must be invariant to later rows in the
        # same file; a global 75-percentile split would look ahead.
        params=dict(target_metric="target",feature_metrics=("feature",),
                    as_of="2025-02-22T00:00:00Z")
        historical=evaluate_issuer_time_holdout(data(dates=53),**params)
        full_file=evaluate_issuer_time_holdout(data(dates=62),**params)
        self.assertEqual(historical["status"],
                         "EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertEqual(full_file,historical)

    def test_future_only_and_unreleased_issuer_do_not_change_asof_result(self):
        params=dict(target_metric="target",feature_metrics=("feature",),
                    as_of="2025-02-22T00:00:00Z")
        baseline=evaluate_issuer_time_holdout(data(dates=53),**params)
        additions=(
            "issuerFuture,feature,2027-01-01T00:00:00Z,2027-01-01T00:00:00Z,3,count\n"
            "issuerFuture,target,2027-01-01T00:00:00Z,2027-01-01T00:00:00Z,4,usd\n"
            "issuerEmbargo,feature,2025-02-19T00:00:00Z,2027-01-01T00:00:00Z,3,count\n"
            "issuerEmbargo,target,2025-02-19T00:00:00Z,2027-01-01T00:00:00Z,4,usd\n"
        ).encode("utf-8")
        expanded=normalize_local_csv(rows(dates=53)+additions,
            dataset_id="fixture",source_id="synthetic",access_level="PUBLIC")
        self.assertEqual(evaluate_issuer_time_holdout(expanded,**params),baseline)

    def test_short_asof_history_must_not_borrow_future_dates_for_split(self):
        result=evaluate_issuer_time_holdout(data(),
            target_metric="target",feature_metrics=("feature",),
            as_of="2025-02-10T00:00:00Z")
        self.assertEqual(result["status"],"NO_TRAIN")
        self.assertEqual(result["reason"],"INSUFFICIENT_DISTINCT_TIMES")
        self.assertEqual(result["guard"],"HOLD")
        self.assertNotIn("holdout_mae",result)

    def test_group_time_holdout_stability_summary_no_raw_identifiers(self):
        r=evaluate_issuer_time_holdout(data(),target_metric="target",
            feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
        d=r["holdout_stability"]
        self.assertEqual(d["holdout_issuer_count"],r["holdout_issuer_count"])
        self.assertEqual(d["model_better_issuer_count"]+
                         d["dummy_better_issuer_count"]+d["tied_issuer_count"],
                         r["holdout_issuer_count"])
        self.assertGreaterEqual(d["distinct_holdout_times"],4)
        self.assertFalse(d["stability_certified"])
        self.assertNotIn("issuer0",str(d))
        self.assertNotIn("fixture",str(d))
        self.assertEqual(r["guard"],"HOLD")

    def test_late_regime_shift_is_explicitly_flagged(self):
        r=evaluate_issuer_time_holdout(data(late_drift=True),
            target_metric="target",feature_metrics=("feature",),
            as_of="2026-01-01T00:00:00Z")
        self.assertEqual(r["status"],"EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertEqual(r["holdout_stability"]["late_error_warning"],
                         "ELEVATED_LATE_ERROR")
        self.assertGreater(r["holdout_stability"]["later_over_earlier_mae_ratio"],2)
        self.assertFalse(r["production_ready"])
        self.assertEqual(r["guard"],"HOLD")

    def test_large_next_observation_interval_mismatch_blocks_training(self):
        # A row-to-row next-label is not a comparable horizon when some
        # issuers/times jump three days and others one day.
        r=evaluate_issuer_time_holdout(data(cadence="mixed"),
            target_metric="target",feature_metrics=("feature",),
            as_of="2026-01-01T00:00:00Z")
        self.assertEqual(r["status"],"NO_TRAIN")
        self.assertEqual(r["reason"],"INCONSISTENT_NEXT_OBSERVATION_HORIZON")
        self.assertEqual(r["guard"],"HOLD")
        self.assertNotIn("holdout_mae",r)
        self.assertNotIn("horizon_uniformity_policy",r)
        self.assertFalse(r["production_ready"])

    def test_month_like_calendar_variation_is_accepted_but_not_validated(self):
        r=evaluate_issuer_time_holdout(data(cadence="month"),
            target_metric="target",feature_metrics=("feature",),
            as_of="2035-01-01T00:00:00Z")
        self.assertEqual(r["status"],"EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertEqual(r["horizon_uniformity_policy"],
                         "INTERVAL_MAX_DIV_MIN_AT_MOST_1_15")
        self.assertEqual(r["observed_horizon_min_days"],29.0)
        self.assertEqual(r["observed_horizon_max_days"],31.0)
        self.assertEqual(r["guard"],"HOLD")
        self.assertFalse(r["finance_validity_verified"])
        self.assertFalse(r["production_ready"])

    def test_time_only_negative_control_is_purged_and_visible(self):
        r=evaluate_issuer_time_holdout(data(),target_metric="target",
            feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(r["status"],"EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertEqual(r["cv_time_only_mae"],r["cv_mae"]["time_only_ridge"])
        self.assertTrue(math.isfinite(r["holdout_time_only_mae"]))
        self.assertGreaterEqual(r["holdout_time_only_mae"],0)
        self.assertIn(r["selected_by_cv"],("dummy_mean","ridge_scaled"))
        self.assertIn(r["time_trend_warning"],(
            "FEATURE_MODEL_NOT_SELECTED","TIME_ONLY_BASELINE_AS_GOOD_OR_BETTER",
            "FEATURE_INCREMENTAL_HOLDOUT_OBSERVED_NOT_VALIDATED"))
        if (r["selected_by_cv"]=="ridge_scaled"
                and r["holdout_mae"]>=r["holdout_time_only_mae"]-1e-9):
            self.assertEqual(r["time_trend_warning"],
                             "TIME_ONLY_BASELINE_AS_GOOD_OR_BETTER")
        self.assertFalse(r["production_ready"])
        self.assertEqual(r["guard"],"HOLD")

    def test_time_baseline_cannot_bypass_feature_release_embargo(self):
        r=evaluate_issuer_time_holdout(data(future_features=True),
            target_metric="target",feature_metrics=("feature",),
            as_of="2026-01-01T00:00:00Z")
        self.assertEqual(r["status"],"NO_TRAIN")
        self.assertNotIn("holdout_time_only_mae",r)

    def test_future_feature_never_trains(self):
        r=evaluate_issuer_time_holdout(data(future_features=True),target_metric="target",
            feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(r["status"],"NO_TRAIN")

    def test_future_labels_not_trainable(self):
        r=evaluate_issuer_time_holdout(data(late_labels=True),target_metric="target",
            feature_metrics=("feature",),as_of="2025-03-05T00:00:00Z")
        self.assertEqual(r["status"],"NO_TRAIN")

    def test_issuers_and_times_minimum(self):
        for kwargs in ({"issuers":7},{"dates":40}):
            r=evaluate_issuer_time_holdout(data(**kwargs),target_metric="target",
                feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
            self.assertEqual(r["status"],"NO_TRAIN")

    def test_lineage_tampering_blocked(self):
        d=data();d["records"][0]["access_level"]="PRIVATE"
        with self.assertRaisesRegex(ValueError,"GROUP_ML_LINEAGE_INVALID"):
            evaluate_issuer_time_holdout(d,target_metric="target",feature_metrics=("feature",),
                as_of="2026-01-01T00:00:00Z")

    def test_units_tampering_blocked(self):
        d=data();d["records"][0]["unit"]="usd"
        with self.assertRaisesRegex(ValueError,"GROUP_ML_UNIT_CONFLICT"):
            evaluate_issuer_time_holdout(d,target_metric="target",feature_metrics=("feature",),
                as_of="2026-01-01T00:00:00Z")

    def test_target_identical_metric_denied(self):
        with self.assertRaisesRegex(ValueError,"GROUP_ML_CONTRACT_INVALID"):
            evaluate_issuer_time_holdout(data(),target_metric="target",feature_metrics=("target",),
                as_of="2026-01-01T00:00:00Z")

    def test_owner_local_acl_and_egress_mock(self):
        v=OwnerLocalGateway("fundA")
        with patch.object(socket.socket,"connect",side_effect=AssertionError("EGRESS")) as connect:
            v.ingest_csv(OWNER,raw=rows(zone="PRIVATE"),dataset_id="privateA",source_id="fake",
                access_level="PRIVATE")
            r=evaluate_owner_local_group(v,ANALYST,dataset_id="privateA",
                target_metric="target",feature_metrics=("feature",),
                as_of="2026-01-01T00:00:00Z")
            self.assertEqual(r["guard"],"HOLD")
            self.assertFalse(v.export_to_public(OWNER,dataset_id="privateA")["data_disclosed"])
            connect.assert_not_called()
            for principal in (WRONG,UNVERIFIED):
                with self.assertRaisesRegex(PermissionError,"GATEWAY_ACCESS_DENIED"):
                    evaluate_owner_local_group(v,principal,dataset_id="privateA",
                        target_metric="target",feature_metrics=("feature",),
                        as_of="2026-01-01T00:00:00Z")

    def test_hybrid_scope_and_group_model(self):
        v=OwnerLocalGateway("fundA")
        v.ingest_csv(OWNER,raw=rows(),dataset_id="publicA",source_id="fakePublic",
            access_level="PUBLIC")
        v.ingest_csv(OWNER,raw=rows(zone="PRIVATE"),dataset_id="privateA",source_id="fakePrivate",
            access_level="PRIVATE")
        approved,_=_prepare_owner_alias_view(
            v,OWNER,public_dataset_id="publicA",private_dataset_id="privateA",
            public_sha256=v._datasets["publicA"]["source_sha256"],
            private_sha256=v._datasets["privateA"]["source_sha256"],
            aliases={r["entity_id"]:r["entity_id"]
                     for r in v._datasets["publicA"]["records"]},
            as_of="2026-01-01T00:00:00Z")
        r=evaluate_owner_local_hybrid_group(approved,ANALYST,public_dataset_id="publicA",
            private_dataset_id="privateA",target_metric="private.target",
            feature_metrics=("public.feature",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(r["analysis"]["status"],"EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertFalse(r["public_export_allowed"])
        with self.assertRaisesRegex(PermissionError,"GATEWAY_ACCESS_DENIED"):
            evaluate_owner_local_hybrid_group(v,WRONG,public_dataset_id="publicA",
                private_dataset_id="privateA",target_metric="private.target",
                feature_metrics=("public.feature",),as_of="2026-01-01T00:00:00Z")

    def test_negative_control_unrelated_labels_not_claimed(self):
        r=evaluate_issuer_time_holdout(data(random_labels=True),target_metric="target",
            feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(r["guard"],"HOLD")
        self.assertEqual(r["statistical_significance"],"NOT_ESTABLISHED")
        self.assertIsNone(r["calibrated_probability"])
