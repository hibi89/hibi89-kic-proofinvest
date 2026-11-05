"""P228 real AMD GAAP operating-profit review and native Streamlit export."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest

from proofinvest.amd_10k_peer_bridge import actual_amd_official_10k_text_receipt
from proofinvest.amd_nvidia_public_reference import actual_amd_public_newsroom_receipt
from proofinvest.amd_operating_profit_review import review_amd_operating_profit

MODE = "KUODRA · 실제 발행사 종목 직접 입력 (2종 · 제한)"


class AMDOperatingProfitReviewTests(unittest.TestCase):
    def test_actual_audited_operating_margin_not_non_gaap(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_LIVE_OR_PAID_REQUEST")) as net:
            out = review_amd_operating_profit()
            net.assert_not_called()
        self.assertEqual(out["status"], "AMD_AUDITED_OPERATING_MARGIN_HUMAN_ONLY",out)
        self.assertEqual(out["operating_margin_2025_pct"], "10.66")
        self.assertEqual(out["operating_margin_2024_pct"], "7.37")
        self.assertEqual(out["operating_margin_change_pp"], "3.30")
        self.assertEqual(out["operating_income_growth_pct"], "94.42")
        self.assertEqual(out["revenue_growth_pct"], "34.34")
        self.assertTrue(out["mi308_export_charge_2025_unadjusted"])
        self.assertEqual(len(out["nvda_publisher_source_sha256"]), 64)
        self.assertIsNone(out["amd_actual_source_sha256"])
        for k in ("peer_raw_bytes_verified", "peer_rights_verified",
                  "market_rights_verified", "sec_original_identical",
                  "full_sector_comparability_verified", "engine_c_complete",
                  "full_abc_complete", "llm_invoked",
                  "investment_recommendation", "trade_executed"):
            self.assertFalse(out[k],k)
        self.assertEqual(out["guard_policy_preview"], "HOLD")
        self.assertEqual(out["network_requests"], 0)

    def test_wrong_ticker_vintage_and_mutated_10k_or_release_rejected(self):
        self.assertEqual(review_amd_operating_profit(ticker="DELL")["status"],"BLOCKED")
        self.assertEqual(review_amd_operating_profit(
            reviewed_as_of="2026-11-04")["status"], "BLOCKED")
        receipt = actual_amd_official_10k_text_receipt()
        for k,v in (("published","2026-10-01"),
                    ("source_rights_verified",True),
                    ("facts",{**receipt["facts"],"gaap_operating_income_2025":"7768"})):
            changed=deepcopy(receipt); changed[k]=v
            with self.subTest(k=k):
                self.assertEqual(review_amd_operating_profit(
                    amd_10k=changed)["status"],"BLOCKED")
        press=actual_amd_public_newsroom_receipt()
        press["facts"]["gaap_operating_income_2024"]="8000"
        self.assertEqual(review_amd_operating_profit(
            amd_release=press)["status"],"BLOCKED")

    def test_independent_nvidia_amd_intel_chain_failure_blocks(self):
        with patch("proofinvest.amd_operating_profit_review.review_two_official_10k_peers",
                   return_value={"status":"BLOCKED"}):
            self.assertEqual(review_amd_operating_profit()["status"],"BLOCKED")
        with patch("proofinvest.amd_operating_profit_review.compare_nvda_amd_audited_10k_peer",
                   return_value={"status":"BLOCKED"}):
            self.assertEqual(review_amd_operating_profit()["status"],"BLOCKED")

    def test_native_nvda_only_real_op_margin_not_deployed_advice(self):
        from streamlit.testing.v1 import AppTest
        app=Path(__file__).resolve().parents[1]/"streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True):
            at=AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(MODE).run(timeout=30)
            next(x for x in at.text_input if x.key=="p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception,[str(x.message) for x in at.exception])
            self.assertTrue(any("AMD 영업이익률" in x.value for x in at.subheader))
            self.assertTrue(any(x.label=="AMD FY2025 GAAP 영업이익률 (%)"
                                and x.value=="10.66" for x in at.metric))
            next(x for x in at.text_input if x.key=="p218_real_issuer_input").set_value("DELL").run(timeout=30)
            self.assertFalse(at.exception)
            self.assertFalse(any("AMD 영업이익률" in x.value for x in at.subheader))

    def test_invalid_source_does_not_show_native_success_metrics(self):
        from streamlit.testing.v1 import AppTest
        app=Path(__file__).resolve().parents[1]/"streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True), patch(
                   "proofinvest.amd_operating_profit_review.review_amd_operating_profit",
                   return_value={"status":"BLOCKED"}):
            at=AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(MODE).run(timeout=30)
            next(x for x in at.text_input if x.key=="p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception)
            self.assertFalse(any("AMD 영업이익률" in x.value for x in at.subheader))
            self.assertFalse(any(x.label=="AMD FY2025 GAAP 영업이익률 (%)" for x in at.metric))
