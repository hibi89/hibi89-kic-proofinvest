"""P227: actual AMD Data Center GAAP segment peer reference, not licensed C."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest

from proofinvest.amd_10k_peer_bridge import actual_amd_official_10k_text_receipt
from proofinvest.amd_nvidia_public_reference import actual_amd_public_newsroom_receipt
from proofinvest.amd_datacenter_segment_bridge import review_amd_datacenter_segment

MODE = "KUODRA · 실제 발행사 종목 직접 입력 (2종 · 제한)"


class AMDDataCenterSegmentTests(unittest.TestCase):
    def test_actual_two_source_segment_growth_is_independent_of_total(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_VENDOR_OR_SEC_HTTP")) as network:
            out = review_amd_datacenter_segment()
            network.assert_not_called()
        self.assertEqual(out["status"], "AMD_DATACENTER_ACTUAL_10K_SEGMENT_HUMAN_REVIEW_ONLY", out)
        self.assertEqual(out["data_center_revenue_2025_usdm"], "16635")
        self.assertEqual(out["data_center_revenue_2024_usdm"], "12579")
        self.assertEqual(out["segment_growth_pct"], "32.24")
        self.assertEqual(out["segment_share_of_amd_revenue_2025_pct"], "48.02")
        self.assertEqual(out["segment_share_of_amd_revenue_2024_pct"], "48.78")
        self.assertEqual(out["segment_share_change_pp"], "-0.76")
        self.assertTrue(out["two_first_party_amd_documents_manually_reconciled"])
        self.assertEqual(len(out["nvda_publisher_source_sha256"]), 64)
        self.assertIsNone(out["peer_source_raw_sha256"])
        self.assertFalse(out["nvda_vs_amd_segment_comparable"])
        for key in (
            "source_raw_bytes_verified", "peer_rights_verified",
            "market_rights_verified", "financial_comparability_verified",
            "representative_peers_verified", "engine_c_complete",
            "full_abc_complete", "ai_agent_executed",
            "investment_recommendation", "trade_executed",
        ):
            self.assertFalse(out[key], key)
        self.assertEqual(out["guard_policy_preview"], "HOLD")
        self.assertEqual(out["network_requests"], 0)

    def test_forged_audited_10k_and_separate_issuer_release_fail_closed(self):
        tenk = actual_amd_official_10k_text_receipt()
        for key, value in (
            ("facts", {**tenk["facts"], "data_center_revenue_2025": "99999"}),
            ("fiscal_latest_end", "2026-01-25"),
            ("source_original_bytes_verified", True),
            ("source_rights_verified", True),
        ):
            with self.subTest(key=key):
                changed = deepcopy(tenk)
                changed[key] = value
                self.assertEqual(review_amd_datacenter_segment(
                    amd_10k=changed)["status"], "BLOCKED")
        press = actual_amd_public_newsroom_receipt()
        press["facts"]["data_center_revenue_2024"] = "99999"
        self.assertEqual(review_amd_datacenter_segment(
            amd_release=press)["status"], "BLOCKED")

    def test_wrong_ticker_vintage_or_upstream_peer_failure_blocks(self):
        self.assertEqual(review_amd_datacenter_segment(
            ticker="DELL")["status"], "BLOCKED")
        self.assertEqual(review_amd_datacenter_segment(
            reviewed_as_of="2026-11-04")["status"], "BLOCKED")
        with patch("proofinvest.amd_datacenter_segment_bridge.review_two_official_10k_peers",
                   return_value={"status":"BLOCKED"}):
            self.assertEqual(review_amd_datacenter_segment()["status"], "BLOCKED")
        with patch("proofinvest.amd_datacenter_segment_bridge.compare_nvda_amd_audited_10k_peer",
                   return_value={"status":"BLOCKED"}):
            self.assertEqual(review_amd_datacenter_segment()["status"], "BLOCKED")

    def test_native_streamlit_real_issuer_nvda_segment_only(self):
        from streamlit.testing.v1 import AppTest
        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True):
            at = AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(MODE).run(timeout=30)
            next(x for x in at.text_input
                 if x.key == "p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            self.assertTrue(any("AMD 데이터센터" in x.value for x in at.subheader))
            self.assertTrue(any(x.label == "AMD 데이터센터 FY2025 성장률 (%)"
                                and x.value == "32.24" for x in at.metric))
            next(x for x in at.text_input
                 if x.key == "p218_real_issuer_input").set_value("DELL").run(timeout=30)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            self.assertFalse(any("AMD 데이터센터" in x.value for x in at.subheader))

    def test_segment_source_failure_removes_success_metrics(self):
        from streamlit.testing.v1 import AppTest
        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True), patch(
                   "proofinvest.amd_datacenter_segment_bridge.review_amd_datacenter_segment",
                   return_value={"status": "BLOCKED"}):
            at = AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(MODE).run(timeout=30)
            next(x for x in at.text_input
                 if x.key == "p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception)
            self.assertFalse(any("AMD 데이터센터" in x.value for x in at.subheader))
            self.assertFalse(any(x.label == "AMD 데이터센터 FY2025 성장률 (%)"
                                 for x in at.metric))
