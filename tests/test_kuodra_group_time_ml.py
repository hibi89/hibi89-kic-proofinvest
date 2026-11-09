"""Issuer/time heldout synthetic backend acceptance and negative controls."""
import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
import socket
from unittest import TestCase
from unittest.mock import patch

from proofinvest.kuodra_unified_core import normalize_local_csv
from proofinvest.kuodra_group_time_ml import (
    evaluate_issuer_time_holdout, evaluate_owner_local_group,
    evaluate_owner_local_hybrid_group)
from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal

OWNER=VerifiedPrincipal("ownerA","fundA",("owner",),True)
ANALYST=VerifiedPrincipal("analystA","fundA",("analyst",),True)
WRONG=VerifiedPrincipal("analystB","fundB",("analyst",),True)
UNVERIFIED=VerifiedPrincipal("anon","fundA",("analyst",),False)


def rows(*, issuers=10, dates=62, zone="PUBLIC", future_features=False,
         late_labels=False, duplicate_target=False, random_labels=False):
    output=StringIO(newline="")
    w=csv.writer(output,lineterminator="\n")
    w.writerow(("entity_id", "metric_id", "observation_at", "available_at", "value", "unit"))
    for j in range(issuers):
        for i in range(dates):
            t=datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(days=i)
            obs=t.strftime("%Y-%m-%dT%H:%M:%SZ")
            feature_release=(t+timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ") if future_features else obs
            target_release=(t+timedelta(days=80)).strftime("%Y-%m-%dT%H:%M:%SZ") if late_labels else obs
            x=i+j*0.4
            y=(j*33+i*27)%97 if random_labels else (i*3 + j*2 + 4)
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
        r=evaluate_owner_local_hybrid_group(v,ANALYST,public_dataset_id="publicA",
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
