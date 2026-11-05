"""P223 actual Intel audited 10-K and second report + AMD peer cohort."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest
from proofinvest.intel_amd_peer_cohort import (
    actual_intc_audited_10k_text_receipt, actual_intc_separate_earnings_receipt,
    review_two_official_10k_peers,
)
MODE = "KUODRA · 실제 발행사 종목 직접 입력 (2종 · 제한)"


class IntelSecondAuditedPeerTests(unittest.TestCase):
    def test_two_real_official_peers_and_nvda_historical_source_replay(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("EXTERNAL_HTTP_FORBIDDEN")) as net:
            out = review_two_official_10k_peers()
            net.assert_not_called()
        self.assertEqual(out["status"], "TWO_DISTINCT_AUDITED_PEER_REFERENCES_LIMITED", out)
        self.assertEqual(out["peer_count"], 2)
        self.assertTrue(out["two_distinct_official_10k_peers_confirmed"])
        self.assertTrue(out["independent_official_release_reconciliation"])
        self.assertEqual(out["intel_filing_accession"], "0000050863-26-000011")
        self.assertEqual(out["intel_2025_revenue_usdm"], "52853")
        self.assertEqual(out["intel_2024_revenue_usdm"], "53101")
        self.assertEqual(out["intel_2025_gross_profit_usdm"], "18375")
        self.assertEqual(out["intel_2024_gross_profit_usdm"], "17345")
        self.assertEqual(out["intel_2025_gross_margin_pct"], "34.77")
        self.assertEqual(out["intel_2024_gross_margin_pct"], "32.66")
        self.assertEqual([x["ticker"] for x in out["revenue_growth_observations_not_sector_rank"]],
                         ["NVDA", "AMD", "INTC"])
        self.assertEqual([x["revenue_growth_pct"] for x in out["revenue_growth_observations_not_sector_rank"]],
                         ["65.47", "34.34", "-0.47"])
        self.assertEqual(out["observed_nvda_minus_amd_growth_pp"], "31.14")
        self.assertEqual(out["observed_nvda_minus_intc_growth_pp"], "65.94")
        self.assertEqual(out["fiscal_end_offsets_days"], {"AMD": 29, "INTC": 29})
        self.assertEqual(len(out["real_nvda_issuer_original_source_sha256"]), 64)
        self.assertTrue(out["intel_altera_2025_deconsolidation_not_adjusted"])
        for key in ("peer_sources_raw_byte_verified", "peer_rights_verified",
                    "representative_peers_verified", "legal_model_input_rights_verified",
                    "market_ndx_rights_verified", "engine_c_complete",
                    "full_abc_complete", "trade_executed", "investment_recommendation"):
            self.assertFalse(out[key], key)
        self.assertEqual(out["guard_policy_preview"], "HOLD")
        self.assertEqual(out["network_requests"], 0)

    def test_tampered_filing_and_independent_release_block(self):
        filing = actual_intc_audited_10k_text_receipt()
        for key,value in (
            ("accession", "0000050863-26-000012"),
            ("issuer_cik", "0000000000"),
            ("source_url", "https://example.org"),
            ("report_filed", "2026-11-06"),
            ("actual_raw_bytes_sha256", "a"*64),
            ("commercial_ai_rights_verified", True),
            ("facts", {**filing["facts"], "revenue_2025": "99999"}),
        ):
            with self.subTest(key=key):
                forged = deepcopy(filing)
                forged[key] = value
                self.assertEqual(review_two_official_10k_peers(
                    intel_10k=forged)["status"], "BLOCKED")
        press = actual_intc_separate_earnings_receipt()
        press["facts"]["gross_profit_2024"] = "99999"
        self.assertEqual(review_two_official_10k_peers(
            intel_release=press)["status"], "BLOCKED")

    def test_wrong_ticker_or_review_date_rejected(self):
        for ticker,asof in (("DELL","2026-11-05"),
                            ("NVDA","2026-11-06"),
                            ("INTC","2026-11-05")):
            self.assertEqual(review_two_official_10k_peers(
                ticker=ticker,reviewed_as_of=asof)["status"], "BLOCKED")

    def test_underlying_amd_source_failure_blocks_aggregated_cohort(self):
        with patch("proofinvest.intel_amd_peer_cohort.compare_nvda_amd_audited_10k_peer",
                   return_value={"status":"BLOCKED"}):
            self.assertEqual(review_two_official_10k_peers()["status"], "BLOCKED")

    def test_genuine_native_issuer_ui_nvda_only_and_intc_caveats(self):
        from streamlit.testing.v1 import AppTest
        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True):
            at = AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(MODE).run(timeout=30)
            next(x for x in at.text_input if x.key == "p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception,[str(x.message) for x in at.exception])
            self.assertTrue(any("NVIDIA / AMD / Intel" in x.value for x in at.subheader))
            self.assertTrue(any("Intel Altera" in x.value for x in at.caption))
            self.assertTrue(any(x.label == "Intel 2025 GAAP 매출총이익률 (%)"
                                and x.value == "34.77" for x in at.metric))
            next(x for x in at.text_input if x.key == "p218_real_issuer_input").set_value("DELL").run(timeout=30)
            self.assertFalse(at.exception,[str(x.message) for x in at.exception])
            self.assertFalse(any("NVIDIA / AMD / Intel" in x.value for x in at.subheader))

    def test_unverified_peer_cannot_masquerade_as_successful_ui(self):
        from streamlit.testing.v1 import AppTest
        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True), patch(
                   "proofinvest.intel_amd_peer_cohort.review_two_official_10k_peers",
                   return_value={"status":"BLOCKED"}):
            at = AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(MODE).run(timeout=30)
            next(x for x in at.text_input if x.key=="p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception)
            self.assertTrue(any("NVDA" in x.value for x in at.success))
            self.assertFalse(any("NVIDIA / AMD / Intel" in x.value for x in at.subheader))
            self.assertTrue(any("두 동종기업의 공식 10-K 검산이 실패" in x.value
                                for x in at.warning))


if __name__ == "__main__":
    unittest.main()
