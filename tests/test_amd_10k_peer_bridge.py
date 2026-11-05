"""P222: official AMD 10-K compared to prior AMD press + genuine NVDA source."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest

from proofinvest.amd_10k_peer_bridge import (
    actual_amd_official_10k_text_receipt,
    compare_nvda_amd_audited_10k_peer,
)
from proofinvest.amd_nvidia_public_reference import actual_amd_public_newsroom_receipt
from proofinvest.nvidia_real_issuer_review import actual_nvidia_issuer_receipt

MODE = "KUODRA · 실제 발행사 종목 직접 입력 (2종 · 제한)"


class AMD10KCrossDocumentPeerTests(unittest.TestCase):
    def test_official_audited_filing_and_press_reconcile_with_actual_nvda(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_GET")) as net:
            r = compare_nvda_amd_audited_10k_peer()
            net.assert_not_called()
        self.assertEqual(r["status"], "ONE_REAL_AUDITED_10K_PEER_CROSSCHECK_ONLY", r)
        self.assertTrue(r["amd_two_independent_official_documents_reconciled"])
        self.assertEqual(r["amd_filing_accession"], "0000002488-26-000018")
        self.assertEqual(r["amd_revenue_2025_usdm"], "34639")
        self.assertEqual(r["amd_gaap_net_income_2025_usdm"], "4335")
        self.assertEqual(r["amd_gaap_net_margin_2025_pct"], "12.51")
        self.assertEqual(r["amd_gaap_net_margin_2024_pct"], "6.36")
        self.assertEqual(r["nvda_revenue_growth_pct"], "65.47")
        self.assertEqual(r["amd_revenue_growth_pct"], "34.34")
        self.assertEqual(r["observed_growth_gap_pp_not_sector_rank"], "31.14")
        self.assertEqual(r["current_fiscal_end_gap_days"], 29)
        self.assertTrue(r["single_peer_not_representative"])
        self.assertEqual(len(r["nvda_original_source_sha256"]), 64)
        for key in ("source_raw_bytes_authenticated", "sec_edgar_original_identical",
                    "peer_rights_verified", "market_ndx_rights_verified",
                    "representative_sector_set", "financial_policies_fully_comparable",
                    "engine_c_complete", "full_abc_complete", "trade_executed"):
            self.assertFalse(r[key], key)
        self.assertEqual(r["guard_policy_preview"], "HOLD")
        self.assertEqual(r["network_requests"], 0)

    def test_forged_audited_filing_press_identity_and_nvda_source_fail_closed(self):
        baseline = actual_amd_official_10k_text_receipt()
        for key, value in (
            ("filing_accession", "0000002488-26-000021"),
            ("fiscal_latest_end", "2026-01-25"),
            ("official_issuer_10k_url", "https://example.com"),
            ("published", "2026-11-06"),
            ("source_original_bytes_verified", True),
            ("source_rights_verified", True),
            ("facts", {**baseline["facts"], "gaap_net_income_2025": "9999"}),
        ):
            x = deepcopy(baseline)
            x[key] = value
            with self.subTest(key=key):
                r = compare_nvda_amd_audited_10k_peer(amd_10k_receipt=x)
                self.assertEqual(r["status"], "BLOCKED", r)
        pub = actual_amd_public_newsroom_receipt()
        pub["facts"]["revenue_2025"] = "9999"
        self.assertEqual(compare_nvda_amd_audited_10k_peer(
            amd_press_receipt=pub)["status"], "BLOCKED")
        nv = actual_nvidia_issuer_receipt()
        nv["source_sha256"] = "0" * 64
        self.assertEqual(compare_nvda_amd_audited_10k_peer(
            nvda_receipt=nv)["status"], "BLOCKED")

    def test_wrong_issuer_or_date_cannot_claim_real_peer(self):
        for ticker, date in (("AMD", "2026-11-05"),
                             ("DELL", "2026-11-05"),
                             ("NVDA", "2026-11-06")):
            with self.subTest(ticker=ticker, date=date):
                r = compare_nvda_amd_audited_10k_peer(
                    ticker=ticker, reviewed_as_of=date)
                self.assertEqual(r["status"], "BLOCKED")
                self.assertFalse(r["engine_c_complete"])

    def test_native_streamlit_ticker_panel_only_nvda(self):
        from streamlit.testing.v1 import AppTest
        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with patch(
            "proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
            return_value=True,
        ):
            at = AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(MODE).run(timeout=30)
            next(x for x in at.text_input if x.key == "p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            self.assertTrue(any("AMD 공식 10-K" in x.value for x in at.subheader))
            self.assertTrue(any(x.label == "AMD FY2025 GAAP 순이익률 (%)"
                                and x.value == "12.51" for x in at.metric))
            next(x for x in at.text_input if x.key == "p218_real_issuer_input").set_value("DELL").run(timeout=30)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            self.assertFalse(any("AMD 공식 10-K" in x.value for x in at.subheader))

    def test_forged_peer_does_not_hide_valid_original_nvda(self):
        from streamlit.testing.v1 import AppTest
        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True), patch(
            "proofinvest.amd_10k_peer_bridge.compare_nvda_amd_audited_10k_peer",
            return_value={"status": "BLOCKED"}):
            at = AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(MODE).run(timeout=30)
            next(x for x in at.text_input if x.key == "p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            self.assertTrue(any("NVDA" in x.value for x in at.success))
            self.assertTrue(any("AMD 독립 10-K/실적발표 교차검산이 실패" in x.value
                                for x in at.warning))
            self.assertFalse(any("AMD 공식 10-K" in x.value for x in at.subheader))


if __name__ == "__main__":
    unittest.main()
