"""SEC Guard + KUODRA restricted ML co-review, synthetic and fail-closed."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import tempfile
from pathlib import Path
from hashlib import sha256
import json
import socket
import unittest
from unittest.mock import patch

from proofinvest.kuodra_review_report import _canonical
from proofinvest.kuodra_sec_ml_review_bridge import (
    build_local_sec_ml_review, render_local_sec_ml_review_html)


def sec(decision="HOLD", numeric="calculated_unverified"):
    return {
        "schema": "proofinvest.local-sec-guard-report.v1",
        "mode": "OFFLINE_USER_SUPPLIED_UNAUTHENTICATED",
        "issuer": {"cik": "SENSITIVE_ISSUER_0000000001"},
        "source": {
            "submissions_sha256": "a"*64,
            "history_page_sha256": "b"*64,
            "companyfacts_sha256": "c"*64,
            "archived_original_sha256": "d"*64,
            "exact_raw_byte_span_verified": True,
            "untrusted_html_text": "PRIVATE SEC RAW CONTENT"},
        "verification": {"status": numeric,
                         "current_amount": "PRIVATE_NOT_FOR_REPORT"},
        "guard": {"decision": decision, "source_authenticated": False,
                  "reason_codes": ["SECRET_OR_ISSUER_NAMES"]},
        "audit_chain_valid": True,
        "human_review_integrity_valid": True,
        "limits": dict.fromkeys(("external_source_authenticated", "source_rights_verified",
           "live_api_called", "ai_agent_executed", "trade_executed",
           "simulation_authorized", "official_contest_submission"), False),
    }


def ml(scope="PRIVATE", status="NO_TRAIN"):
    data={"schema":"kuodra.local-restricted-review.v1",
          "status":"HUMAN_REVIEW_REQUIRED","scope":scope,
          "as_of":"2026-11-01T00:00:00Z", "decision":"HOLD",
          "public_export_allowed":False,"external_llm_allowed":False,
          "host_egress_verified":False,"origin_verified":False,
          "calibrated_probability":None,"data_rows_disclosed":False,
          "analysis":{"status":status,"train_n":0,"holdout_n":0,
                      "holdout_improvement_pct":None,
                      "feature_metrics":"SENSITIVE_FEATURE_NAME"},
          "evidence":[{"raw_source_sha256":"e"*64,"row_count":42,
                       "access_level":"PRIVATE","publisher_authenticated":False,
                       "source_rights_verified":False}],
          "secret_canary":"MY_PRIVATE_SECRET_DO_NOT_EXPORT"}
    if scope=="LOCAL_HYBRID":
        data["evidence"].insert(0,{"raw_source_sha256":"f"*64,"row_count":43,
                                  "access_level":"PUBLIC","publisher_authenticated":False,
                                  "source_rights_verified":False})
    data["receipt_sha256"]=sha256(_canonical(data)).hexdigest()
    return data


class SecMLBridgeTest(unittest.TestCase):
    def test_hold_report_keeps_independent_provenance(self):
        report=build_local_sec_ml_review(sec(),ml())
        self.assertEqual(report["decision"],"HOLD")
        self.assertEqual(report["cross_source_entity_link"],
             "NOT_ESTABLISHED_DO_NOT_JOIN_OR_COMPARE_ISSUERS")
        self.assertFalse(report["public_export_allowed"])
        self.assertFalse(report["trade_authorized"])
        self.assertEqual(report["ml"]["summary"]["status"],"NO_TRAIN")
        self.assertEqual(len(report["sec"]["source_hashes"]),4)

    def test_sec_conflict_reject_never_overridden_by_ml(self):
        report=build_local_sec_ml_review(sec("REJECT","conflict"),
                ml(status="EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED"))
        self.assertEqual(report["decision"],"REJECT")

    def test_sec_conflict_downgrade_detected(self):
        with self.assertRaisesRegex(ValueError,"BRIDGE_SEC_CONFLICT_DOWNGRADED"):
            build_local_sec_ml_review(sec("HOLD","conflict"),ml())

    def test_sec_audit_tampering_denied(self):
        invalid=sec();invalid["audit_chain_valid"]=False
        with self.assertRaisesRegex(ValueError,"BRIDGE_SEC_AUDIT_OR_SOURCE_INVALID"):
            build_local_sec_ml_review(invalid,ml())

    def test_sec_report_with_fake_auth_or_trade_denied(self):
        invalid=sec();invalid["limits"]["external_source_authenticated"]=True
        with self.assertRaisesRegex(ValueError,"BRIDGE_SEC_UNTRUSTED_POLICY"):
            build_local_sec_ml_review(invalid,ml())

    def test_malformed_original_source_digest_denied(self):
        invalid=sec(); invalid["source"]["companyfacts_sha256"]="notsha"
        with self.assertRaisesRegex(ValueError,"BRIDGE_SEC_EVIDENCE_INVALID"):
            build_local_sec_ml_review(invalid,ml())

    def test_ml_integrity_corruption_denied(self):
        invalid=ml(); invalid["analysis"]["holdout_n"]=777
        with self.assertRaisesRegex(ValueError,"BRIDGE_ML_RECEIPT_INVALID"):
            build_local_sec_ml_review(sec(),invalid)

    def test_ml_restrictive_flags_must_remain(self):
        invalid=ml();invalid["public_export_allowed"]=True
        with self.assertRaisesRegex(ValueError,"BRIDGE_ML_RESTRICTION_INVALID"):
            build_local_sec_ml_review(sec(),invalid)

    def test_hybrid_zone_and_both_digests_retained(self):
        r=build_local_sec_ml_review(sec(),ml("LOCAL_HYBRID"))
        self.assertEqual([s["zone"] for s in r["ml"]["source_hashes"]],
                         ["PUBLIC","PRIVATE"])

    def test_private_raw_identifiers_not_in_report_or_html(self):
        r=build_local_sec_ml_review(sec(),ml())
        html=render_local_sec_ml_review_html(r)
        for token in ("MY_PRIVATE_SECRET", "SENSITIVE_FEATURE_NAME",
                      "SENSITIVE_ISSUER", "PRIVATE SEC RAW CONTENT", "SECRET_OR_ISSUER_NAMES"):
            self.assertNotIn(token,json.dumps(r))
            self.assertNotIn(token,html)
        self.assertIn("default-src 'none'",html)
        self.assertNotIn("<script",html.lower())

    def test_render_tamper_rejected(self):
        r=build_local_sec_ml_review(sec(),ml())
        r["decision"]="REJECT"
        with self.assertRaisesRegex(ValueError,"BRIDGE_RENDER_RECEIPT_INVALID"):
            render_local_sec_ml_review_html(r)

    def test_ml_numeric_injection_rejected_even_with_rehashed_packet(self):
        invalid=ml();invalid["analysis"]["train_n"]=-1
        invalid["receipt_sha256"]=sha256(_canonical({k:v for k,v in invalid.items()
                                                     if k!="receipt_sha256"})).hexdigest()
        with self.assertRaisesRegex(ValueError,"BRIDGE_UNSAFE_ML_SUMMARY"):
            build_local_sec_ml_review(sec(),invalid)

    def test_actual_local_group_ml_packet_accepted(self):
        # Use the real existing group/time ML backend, not a hand-written ML
        # dict, to guard against version/contract drift at the adapter edge.
        from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
        from proofinvest.kuodra_review_report import build_owner_group_review
        from test_kuodra_group_time_ml import rows
        owner=VerifiedPrincipal("ownerA", "fundA", ("owner",), True)
        analyst=VerifiedPrincipal("analystA", "fundA", ("analyst",), True)
        gateway=OwnerLocalGateway("fundA")
        gateway.ingest_csv(owner, raw=rows(zone="PRIVATE"),
            dataset_id="actualSecret", source_id="generated", access_level="PRIVATE")
        actual_ml=build_owner_group_review(gateway, analyst,
            private_dataset_id="actualSecret", target_metric="target",
            feature_metrics=("feature",), as_of="2026-01-01T00:00:00Z")
        combined=build_local_sec_ml_review(sec(), actual_ml)
        self.assertEqual(combined["ml"]["summary"]["status"],
                         "EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertEqual(combined["decision"],"HOLD")
        self.assertNotIn("actualSecret",str(combined))

    @unittest.skipUnless(importlib.util.find_spec("proofinvest.local_sec_guard_report"),
                         "full SEC local Guard sources not mounted in focused test workspace")
    def test_full_existing_sec_guard_plus_actual_ml_end_to_end(self):
        # Executes in the original repository's full test environment, with
        # its already-existing synthetic SEC 4-source fixture + SQLite audit.
        # No real SEC endpoint, real customer data, or provider request.
        from proofinvest.local_sec_guard_report import review_local_sec_with_guard
        from test_local_sec_guard_report import fixture
        from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
        from proofinvest.kuodra_review_report import build_owner_group_review
        from test_kuodra_group_time_ml import rows
        owner=VerifiedPrincipal("ownerA","fundA",("owner",),True)
        analyst=VerifiedPrincipal("analystA","fundA",("analyst",),True)
        vault=OwnerLocalGateway("fundA")
        vault.ingest_csv(owner,raw=rows(zone="PRIVATE"),dataset_id="privateA",
                         source_id="fictionalSource",access_level="PRIVATE")
        ml_packet=build_owner_group_review(vault,analyst,private_dataset_id="privateA",
            target_metric="target",feature_metrics=("feature",),
            as_of="2026-01-01T00:00:00Z")
        for claim, expected in (("100.00","HOLD"),("300.00","REJECT")):
            with self.subTest(claim=claim), tempfile.TemporaryDirectory() as folder:
                arguments=fixture(Path(folder)/"audit.sqlite")
                arguments["claimed_growth_pct"]=claim
                sec_report=review_local_sec_with_guard(**arguments)
                combined=build_local_sec_ml_review(sec_report,ml_packet)
                self.assertEqual(combined["decision"],expected)
                self.assertTrue(combined["sec"]["offline_audit_chain_verified"])
                self.assertFalse(combined["independent_finance_validation"])
                self.assertEqual(combined["cross_source_entity_link"],
                   "NOT_ESTABLISHED_DO_NOT_JOIN_OR_COMPARE_ISSUERS")
                html=render_local_sec_ml_review_html(combined)
                self.assertIn(expected,html)
                self.assertNotIn("privateA",html)

    def test_mock_socket_no_network_calls(self):
        with patch.object(socket.socket,"connect",side_effect=AssertionError("NETWORK")) as connect:
            r=build_local_sec_ml_review(sec(),ml())
            render_local_sec_ml_review_html(r)
            connect.assert_not_called()


if __name__=="__main__":
    unittest.main()