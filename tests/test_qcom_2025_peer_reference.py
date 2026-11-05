"""P230 actual distinct third public Qualcomm FY2025 10-K (manual text) peer."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest

from proofinvest.qcom_2025_peer_reference import (
    official_qcom_fy2025_10k_public_text_receipt,
    official_qcom_fy2025_public_release_receipt,
    review_public_qualcomm_third_peer,
)

MODE="KUODRA · 실제 발행사 종목 직접 입력 (2종 · 제한)"


class QualcommThirdPeerTests(unittest.TestCase):
    def test_replayed_third_independent_public_audited_filing_reference(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_EXTERNAL_HTTP")) as network:
            out=review_public_qualcomm_third_peer()
            network.assert_not_called()
        self.assertEqual(out["status"],
                         "THIRD_QCOM_PUBLIC_AUDITED_10K_HUMAN_REFERENCE_ONLY",out)
        self.assertEqual(out["distinct_public_10k_peer_count_descriptive"],3)
        self.assertEqual(out["filing_accession"],"0000804328-25-000085")
        self.assertEqual(out["qcom_revenue_2025_usdm"],"44284")
        self.assertEqual(out["qcom_revenue_2024_usdm"],"38962")
        self.assertEqual(out["qcom_revenue_growth_pct"],"13.66")
        self.assertEqual(out["qcom_gaap_operating_margin_2025_pct"],"27.90")
        self.assertEqual(out["qcom_gaap_operating_margin_2024_pct"],"25.85")
        self.assertEqual(out["qcom_gaap_operating_margin_delta_pp"],"2.05")
        self.assertEqual(out["source_reconciliation_scope"],
                         "ROUNDED_ANNUAL_REVENUE_AND_PERIOD_ONLY")
        self.assertEqual(out["nvda_qcom_fiscal_offset_days"],119)
        self.assertTrue(out["qcom_licensing_component_not_equivalent_to_nvda"])
        self.assertTrue(out["different_business_and_fiscal_windows"])
        self.assertIsNone(out["qcom_10k_raw_sha256"])
        self.assertEqual(len(out["nvda_publisher_source_sha256"]),64)
        self.assertTrue(out["qcom_audited_text_10k_url"].startswith("https://"))
        for key in ("peer_original_raw_verified","sec_original_byte_identical",
                    "peer_rights_verified","representative_peers_verified",
                    "market_rights_verified","legal_model_use_rights_verified",
                    "engine_c_complete","full_abc_complete",
                    "investment_recommendation","trade_executed"):
            self.assertFalse(out[key],key)
        self.assertEqual(out["guard_policy_preview"],"HOLD")
        self.assertEqual(out["network_requests"],0)

    def test_forged_filings_press_and_rights_cannot_pass(self):
        tenk=official_qcom_fy2025_10k_public_text_receipt()
        for key, value in (
            ("filed","2026-11-06"),
            ("accession","0000804328-26-000128"),
            ("source_url","https://invalid.example"),
            ("original_raw_bytes_sha256","f"*64),
            ("source_rights_verified",True),
            ("facts",{**tenk["facts"],"revenue_2025":"99999"}),
        ):
            forged=deepcopy(tenk);forged[key]=value
            with self.subTest(key=key):
                self.assertEqual(review_public_qualcomm_third_peer(
                    qcom_10k=forged)["status"],"BLOCKED")
        press=official_qcom_fy2025_public_release_receipt()
        press["gaap_annual_revenue_rounded_billions"]="99.9"
        self.assertEqual(review_public_qualcomm_third_peer(
            qcom_release=press)["status"],"BLOCKED")

    def test_wrong_ticker_date_or_existing_pair_invalid_blocks(self):
        for kwargs in (
            {"ticker":"DELL"},{"ticker":"QCOM"},
            {"reviewed_as_of":"2026-11-06"},
        ):
            self.assertEqual(review_public_qualcomm_third_peer(
                **kwargs)["status"],"BLOCKED")
        with patch("proofinvest.qcom_2025_peer_reference.review_two_official_10k_peers",
                   return_value={"status":"BLOCKED"}):
            self.assertEqual(review_public_qualcomm_third_peer()["status"],"BLOCKED")
        with patch("proofinvest.qcom_2025_peer_reference.review_supported_real_ticker",
                   return_value={"status":"BLOCKED"}):
            self.assertEqual(review_public_qualcomm_third_peer()["status"],"BLOCKED")

    def test_nvda_native_ui_shows_qcom_only_after_source_validation(self):
        from streamlit.testing.v1 import AppTest
        app=Path(__file__).resolve().parents[1]/"streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True):
            at=AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(MODE).run(timeout=30)
            next(x for x in at.text_input
                 if x.key=="p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception,[str(x.message) for x in at.exception])
            self.assertTrue(any("Qualcomm" in x.value for x in at.subheader))
            self.assertTrue(any(x.label=="QCOM FY2025 GAAP 매출 증가율 (%)"
                                and x.value=="13.66" for x in at.metric))
            next(x for x in at.text_input
                 if x.key=="p218_real_issuer_input").set_value("DELL").run(timeout=30)
            self.assertFalse(at.exception)
            self.assertFalse(any("Qualcomm" in x.value for x in at.subheader))

    def test_source_chain_failure_hides_qcom_metrics_and_export(self):
        from streamlit.testing.v1 import AppTest
        app=Path(__file__).resolve().parents[1]/"streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True),patch(
                   "proofinvest.qcom_2025_peer_reference.review_public_qualcomm_third_peer",
                   return_value={"status":"BLOCKED"}):
            at=AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(MODE).run(timeout=30)
            next(x for x in at.text_input
                 if x.key=="p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception)
            self.assertFalse(any("Qualcomm" in x.value for x in at.subheader))
            self.assertFalse(any(x.key=="p230_qcom_third_peer_export" for x in at.button))
