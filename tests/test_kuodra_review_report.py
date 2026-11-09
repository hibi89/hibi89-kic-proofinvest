"""No secrets/raw rows or cross-owner disclosure in restricted reports."""
import socket
from unittest import TestCase
from unittest.mock import patch
from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from proofinvest.kuodra_review_report import (
    build_owner_group_review, render_restricted_review_html)
from test_kuodra_group_time_ml import rows

OWNER=VerifiedPrincipal("ownerA","fundA",("owner",),True)
ANALYST=VerifiedPrincipal("analystA","fundA",("analyst",),True)
OTHER=VerifiedPrincipal("analystB","fundB",("analyst",),True)

class RestrictedReviewTest(TestCase):
    def setUp(self):
        self.vault=OwnerLocalGateway("fundA")
        self.vault.ingest_csv(OWNER,raw=rows(zone="PRIVATE"),dataset_id="secretDataset",
            source_id="privateFile",access_level="PRIVATE")
        self.vault.ingest_csv(OWNER,raw=rows(),dataset_id="externalDataset",
            source_id="publicFile",access_level="PUBLIC")

    def test_private_report_is_restricted_and_deterministic(self):
        params=dict(private_dataset_id="secretDataset",target_metric="target",
            feature_metrics=("feature",),as_of="2026-01-01T00:00:00Z")
        r=build_owner_group_review(self.vault,ANALYST,**params)
        self.assertEqual(r,build_owner_group_review(self.vault,ANALYST,**params))
        self.assertEqual(r["decision"],"HOLD")
        self.assertEqual(r["scope"],"PRIVATE")
        self.assertFalse(r["public_export_allowed"])
        self.assertFalse(r["data_rows_disclosed"])
        self.assertFalse(r["host_egress_verified"])
        self.assertEqual(len(r["evidence"]),1)
        self.assertIn("time_trend_warning",r["analysis"])
        self.assertIn("holdout_time_only_mae",r["analysis"])
        self.assertEqual(r["analysis"]["observed_horizon_min_days"],1.0)
        self.assertEqual(r["analysis"]["observed_horizon_max_days"],1.0)
        self.assertEqual(r["analysis"]["horizon_uniformity_policy"],
                         "INTERVAL_MAX_DIV_MIN_AT_MOST_1_15")
        for sensitive in ("secretDataset", "privateFile", "issuer0", "ownerA"):
            self.assertNotIn(sensitive,str(r))

    def test_hybrid_report_both_sources_and_no_public_export(self):
        r=build_owner_group_review(self.vault,ANALYST,private_dataset_id="secretDataset",
            public_dataset_id="externalDataset",target_metric="private.target",
            feature_metrics=("public.feature",),as_of="2026-01-01T00:00:00Z")
        self.assertEqual(r["scope"],"LOCAL_HYBRID")
        self.assertEqual(len(r["evidence"]),2)
        self.assertEqual(r["analysis"]["status"],"EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertFalse(r["public_export_allowed"])
        text=render_restricted_review_html(r)
        self.assertIn("HOLD",text)
        self.assertIn("Content-Security-Policy",text)
        self.assertNotIn("secretDataset",text)
        self.assertNotIn("issuer0",text)

    def test_denied_role_and_cross_tenant(self):
        with self.assertRaisesRegex(PermissionError,"GATEWAY_ACCESS_DENIED"):
            build_owner_group_review(self.vault,OTHER,private_dataset_id="secretDataset",
                target_metric="target",feature_metrics=("feature",),
                as_of="2026-01-01T00:00:00Z")

    def test_tampered_packet_fails_closed(self):
        r=build_owner_group_review(self.vault,ANALYST,private_dataset_id="secretDataset",
            target_metric="target",feature_metrics=("feature",),
            as_of="2026-01-01T00:00:00Z")
        r["analysis"]["holdout_mae"]=0
        with self.assertRaisesRegex(ValueError,"REVIEW_REPORT_HASH_MISMATCH"):
            render_restricted_review_html(r)

    def test_mock_socket_no_egress(self):
        with patch.object(socket.socket,"connect",side_effect=AssertionError("EGRESS")) as connect:
            r=build_owner_group_review(self.vault,ANALYST,private_dataset_id="secretDataset",
                target_metric="target",feature_metrics=("feature",),
                as_of="2026-01-01T00:00:00Z")
            render_restricted_review_html(r)
            connect.assert_not_called()
