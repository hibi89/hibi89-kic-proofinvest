"""P219 actual issuer receipts -> locally supplied stock + true NDX symbol OLS."""
from __future__ import annotations

from datetime import date, timedelta
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from proofinvest.real_issuer_local_market import (
    review_real_issuer_local_market_pair, render_real_issuer_local_market_panel,
    verify_derived_ab_checksum,
)


def vendor_form(ticker: str, base: int = 120) -> bytes:
    # Intentionally synthetic prices, distinguish from the REAL issuer facts.
    rows = {}
    day = date(2026, 8, 18)
    i = 0
    while day <= date(2026, 11, 4):
        if day.weekday() < 5:
            rows[day.isoformat()] = {
                "4. close": str(base + i * 2 + (i % 5) * 3)
            }
            i += 1
        day += timedelta(days=1)
    return json.dumps({
        "Meta Data": {"2. Symbol": ticker},
        "Time Series (Daily)": rows,
    }).encode("utf-8")


class RealIssuerOperatorMarketTests(unittest.TestCase):
    def test_each_real_issuer_enters_decimal_ols_without_any_network(self):
        for ticker in ("NVDA", "DELL"):
            with self.subTest(ticker=ticker), patch(
                "urllib.request.urlopen",
                side_effect=AssertionError("NO_PROVIDER_REQUEST"),
            ) as net:
                r = review_real_issuer_local_market_pair(
                    ticker=ticker, stock_json=vendor_form(ticker),
                    ndx_json=vendor_form("NDX", base=10000),
                )
                net.assert_not_called()
                self.assertEqual(r["status"],
                                 "REAL_ISSUER_WITH_LOCAL_NDX_MATH_UNVERIFIED", r)
                self.assertEqual(r["ticker"], ticker)
                self.assertEqual(r["submitted_ndx_symbol"], "NDX")
                self.assertGreaterEqual(r["matched_sessions"], 31)
                self.assertIn(r["engine_a"]["status"], (
                    "REPORTED_UNVERIFIED", "INSUFFICIENT_MARKET_VARIANCE"))
                self.assertEqual(r["network_requests"], 0)
                self.assertEqual(r["guard_policy_preview"], "HOLD")
                self.assertFalse(r["market_rights_verified"])
                self.assertFalse(r["stock_provider_authenticated"])
                self.assertFalse(r["ndx_provider_authenticated"])
                self.assertFalse(r["full_abc_complete"])
                self.assertFalse(r["trade_executed"])
                self.assertNotIn("close_observations", repr(r))
                self.assertNotIn("Meta Data", repr(r))
                self.assertNotIn("apikey", repr(r))
                self.assertTrue(verify_derived_ab_checksum(r))
                self.assertEqual(r["combined_review_schema"],
                                 "kuodra.p220-issuer-financial-market-joined.v1")
                self.assertEqual(r["engine_b"]["issuer_financial_source_sha256"],
                                 r["issuer_source_sha256"])
                self.assertEqual(r["engine_b"]["issuer_source_ci_run"].startswith("https://"), True)
                expected = ("65.47", "0.8555") if ticker == "NVDA" else ("18.80", "1.8843")
                self.assertEqual(r["engine_b"]["revenue_growth_pct"], expected[0])
                self.assertEqual(r["engine_b"]["cashflow_to_net_income_ratio"], expected[1])
                forged = deepcopy(r)
                forged["engine_b"]["revenue_growth_pct"] = "999.99"
                self.assertFalse(verify_derived_ab_checksum(forged))
                self.assertFalse(r["source_authenticated_by_sec"])
                self.assertFalse(r["commercial_reuse_allowed"])

    def test_recomputed_real_issuer_financials_fail_closed_on_mutation(self):
        from proofinvest.real_issuer_ticker_review import review_supported_real_ticker
        actual = review_supported_real_ticker("NVDA")
        self.assertEqual(actual["status"], "REAL_ISSUER_HUMAN_REVIEW_ONLY")
        for key, forged_value in (
            ("issuer_revenue_growth_pct", "66.00"),
            ("cashflow_to_net_income_ratio", "1.0000"),
            ("review_as_of", "2026-11-06"),
            ("financial_review", "FULLY_LICENSED"),
        ):
            with self.subTest(key=key):
                manipulated = dict(actual)
                manipulated[key] = forged_value
                with patch(
                    "proofinvest.real_issuer_local_market.review_supported_real_ticker",
                    return_value=manipulated,
                ):
                    result = review_real_issuer_local_market_pair(
                        ticker="NVDA", stock_json=vendor_form("NVDA"),
                        ndx_json=vendor_form("NDX", base=10000))
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertNotIn("engine_b", result)
                    self.assertEqual(result["guard_policy_preview"], "HOLD")

    def test_wrong_issuer_ndx_qqq_and_as_of_fail_closed(self):
        for ticker, rawstock, rawidx, asof in (
            ("AAPL", vendor_form("NVDA"), vendor_form("NDX", 10000), "2026-11-05"),
            ("NVDA", vendor_form("DELL"), vendor_form("NDX", 10000), "2026-11-05"),
            ("NVDA", vendor_form("NVDA"), vendor_form("QQQ", 10000), "2026-11-05"),
            ("NVDA", vendor_form("NVDA"), vendor_form("NDX", 10000), "2026-11-06"),
            ("DELL", vendor_form("DELL"), b'{"Note":"premium required"}', "2026-11-05"),
        ):
            with self.subTest(ticker=ticker,asof=asof):
                r = review_real_issuer_local_market_pair(
                    ticker=ticker, stock_json=rawstock, ndx_json=rawidx,
                    as_of=asof)
                self.assertEqual(r["status"], "BLOCKED", r)
                self.assertFalse(r["full_abc_complete"])
                self.assertNotIn("engine_a", r)

    def test_fake_original_issuer_and_stale_index_block(self):
        with patch(
            "proofinvest.real_issuer_local_market.review_supported_real_ticker",
            return_value={"status":"BLOCKED"},
        ):
            r = review_real_issuer_local_market_pair(
                ticker="NVDA", stock_json=vendor_form("NVDA"),
                ndx_json=vendor_form("NDX", 10000))
            self.assertEqual(r["status"],"BLOCKED")
        original = json.loads(vendor_form("NDX",10000))
        # Remove all recent data, retaining >31 historical rows:
        original["Time Series (Daily)"]={
            k:v for k,v in original["Time Series (Daily)"].items()
            if k < "2026-10-05"
        }
        r = review_real_issuer_local_market_pair(
            ticker="NVDA", stock_json=vendor_form("NVDA"),
            ndx_json=json.dumps(original).encode())
        self.assertEqual(r["status"],"BLOCKED")

    def test_local_market_panel_render_requires_local_gate(self):
        class St:
            def __init__(self):
                self.events=[]
            def warning(self, v): self.events.append(("warning",v))
            def subheader(self,v): self.events.append(("header",v))
            def caption(self,v): self.events.append(("caption",v))
            def file_uploader(self,*a,**kw):
                self.events.append(("upload", kw["key"]))
                return None
            def checkbox(self,*a,**kw): return False
            def form(self,*a,**kw): return self
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def form_submit_button(self,*a,**kw): return False
            def button(self,*a,**kw): return False
        st=St()
        with patch(
            "proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
            return_value=False,
        ):
            render_real_issuer_local_market_panel(st,ticker="NVDA")
        self.assertFalse(st.events)
        with patch(
            "proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
            return_value=True,
        ):
            render_real_issuer_local_market_panel(st,ticker="NVDA")
        self.assertEqual(len([x for x in st.events if x[0]=="upload"]),2)

    def test_native_streamlit_upload_controls_from_real_issuer(self):
        from pathlib import Path
        from streamlit.testing.v1 import AppTest
        app=Path(__file__).resolve().parents[1]/"streamlit_app.py"
        with patch(
            "proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
            return_value=True,
        ):
            at=AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(
                "KUODRA · 실제 발행사 종목 직접 입력 (2종 · 제한)"
            ).run(timeout=30)
            next(x for x in at.text_input
                 if x.key=="p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception,[str(x.message) for x in at.exception])
            self.assertTrue(any(x.key=="p219_market_local_ack" for x in at.checkbox))
            self.assertTrue(any(x.key=="p219_market_local_review" for x in at.button))
            # A form submit remains clickable, while data validation is
            # enforced on the atomic backend event even if fields are empty.
            self.assertFalse(next(x for x in at.button
                                  if x.key=="p219_market_local_review").disabled)


if __name__=="__main__":
    unittest.main()
