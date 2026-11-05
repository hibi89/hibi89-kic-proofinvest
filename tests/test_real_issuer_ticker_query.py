"""P218: two actual publisher-backed issuers through one typed native user path."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from proofinvest.real_issuer_ticker_review import review_supported_real_ticker

_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_MODE = "KUODRA · 실제 발행사 종목 직접 입력 (2종 · 제한)"


class RealIssuerTickerQueryTests(unittest.TestCase):
    def test_two_real_distinct_issuers_recompute_actual_annual_metrics(self):
        expected = {
            "NVDA": ("65.47", "0.8555", "1.30", "46.86"),
            "DELL": ("18.80", "1.8843", "51.96", "36.60"),
        }
        for ticker, metrics in expected.items():
            with self.subTest(ticker=ticker), patch(
                    "urllib.request.urlopen",
                    side_effect=AssertionError("no external provider HTTP")) as net:
                r = review_supported_real_ticker(ticker.lower())
                net.assert_not_called()
                self.assertEqual(r["status"], "REAL_ISSUER_HUMAN_REVIEW_ONLY", r)
                self.assertEqual(r["ticker"], ticker)
                self.assertEqual(tuple(r[k] for k in (
                    "issuer_revenue_growth_pct",
                    "cashflow_to_net_income_ratio",
                    "receivables_minus_revenue_growth_pp",
                    "inventory_minus_revenue_growth_pp")), metrics)
                self.assertEqual(len(r["source_sha256"]), 64)
                self.assertTrue(r["source_url"].startswith("https://"))
                self.assertTrue(r["publisher_original_observed"])
                self.assertEqual(r["guard_policy_preview"], "HOLD")
                self.assertFalse(r["source_authenticated_by_sec"])
                self.assertFalse(r["source_rights_verified"])
                self.assertFalse(r["market_ndx_peer_licensed"])
                self.assertFalse(r["full_abc_complete"])
                self.assertFalse(r["trade_executed"])
                self.assertEqual(r["market_price_status"], "UNAVAILABLE")
                self.assertEqual(r["ndx_benchmark_status"], "UNAVAILABLE")
                self.assertEqual(r["peer_evidence_status"], "UNAVAILABLE")
                self.assertNotIn("raw_original", r)

    def test_unknown_ticker_and_unreviewed_vintage_not_fabricated(self):
        for ticker in ("AAPL", "AMD", "MSFT", "NVDA.DE", "NVDA\\nBUY", "",
                       None, True, "NVDA " + "X" * 45):
            with self.subTest(ticker=ticker):
                r = review_supported_real_ticker(ticker)
                self.assertEqual(r["status"], "BLOCKED")
                self.assertNotIn("source_sha256", r)
                self.assertFalse(r["investment_recommendation"])
        r = review_supported_real_ticker("NVDA", as_of="2026-11-06")
        self.assertEqual(r["status"], "BLOCKED")

    def test_forged_issuer_review_or_missing_cross_document_gate(self):
        with patch("proofinvest.nvidia_real_issuer_review.review_nvidia_actual_release",
                   return_value={"status": "BLOCKED"}):
            self.assertEqual(
                review_supported_real_ticker("NVDA")["status"], "BLOCKED")
        with patch("proofinvest.dell_working_capital_review.review_real_working_capital",
                   return_value={"status": "BLOCKED"}):
            self.assertEqual(
                review_supported_real_ticker("DELL")["status"], "BLOCKED")

    def test_actual_streamlit_input_switches_issuers_without_network(self):
        from streamlit.testing.v1 import AppTest
        # AppTest cannot bind a real loopback server; retain the existing
        # separately tested local_workspace_enabled predicate as the sole gate.
        with patch(
            "proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
            return_value=True,
        ):
            at = AppTest.from_file(str(_APP)).run(timeout=30)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            at.selectbox[0].set_value(_MODE).run(timeout=30)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            box = next(x for x in at.text_input if x.key == "p218_real_issuer_input")
            box.set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            self.assertTrue(any("NVDA" in x.value for x in at.success))
            self.assertTrue(any(x.label == "연매출 성장률 (발행사 근거)" and
                                x.value == "65.47%" for x in at.metric))
            box = next(x for x in at.text_input if x.key == "p218_real_issuer_input")
            box.set_value("DELL").run(timeout=30)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            self.assertTrue(any("DELL" in x.value for x in at.success))
            self.assertTrue(any(x.label == "연매출 성장률 (발행사 근거)" and
                                x.value == "18.80%" for x in at.metric))
            box = next(x for x in at.text_input if x.key == "p218_real_issuer_input")
            box.set_value("AAPL").run(timeout=30)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            self.assertFalse(at.success)
            self.assertFalse(at.metric)
            self.assertTrue(any("검증 기록이 없거나" in x.value for x in at.warning))


if __name__ == "__main__":
    unittest.main()
