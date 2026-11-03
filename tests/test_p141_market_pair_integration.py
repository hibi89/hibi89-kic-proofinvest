"""P141 full-repository offline integration: actual Decimal Engine A and UI click.

No live SEC or Alpha Vantage requests. This is not licensed data evidence.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from proofinvest.market_pair_engine_a import (
    analyze_price_index_pair, build_market_reality_payload,
)
from proofinvest import ticker_research_ui as ui
from proofinvest import ticker_sec_transport as transport
from tests.test_market_pair_engine_a import sources
from tests.test_ticker_market_industry_bridge import scenario
from tests.test_ticker_research_ui import FakeSt, Uploaded

AV_KEY = "SYNTHETICKEY12345"
GATES = {
    "KUODRA_ENABLE_ALPHA_VANTAGE_DAILY": "1",
    "KUODRA_ENABLE_ALPHA_VANTAGE_INDEX": "1",
    "KUODRA_ALPHA_VANTAGE_INDEX_PREMIUM_APPROVED": "1",
    "KUODRA_ALPHA_VANTAGE_RIGHTS_APPROVED": "1",
    "KUODRA_ALPHA_VANTAGE_API_KEY": AV_KEY,
}
LABEL = "로컬 공시 재검산 + 승인된 주가·실제 NDX 지수 조회 (최대 2회)"


def make_inputs():
    _, raw, market, industry = scenario()
    return {
        "kuodra_p100_ticker_map": Uploaded(raw["ticker_map"]),
        "kuodra_p100_submissions": Uploaded(raw["submissions"]),
        "kuodra_p116_companyfacts": Uploaded(raw["companyfacts"]),
        "kuodra_p116_original": Uploaded(raw["original_10k"]),
    }


class RealEngineAndUiTests(unittest.TestCase):
    def test_genuine_existing_decimal_ols_math_receives_aligned_index(self):
        stock, index = sources()
        result = analyze_price_index_pair(
            stock=stock, index=index, ticker="NVDA", issuer_cik="0001045810",
            filing_date="2026-06-30", as_of="2026-10-01",
        )
        self.assertEqual(result["status"], "ENGINE_A_PRICE_INDEX_DESCRIPTIVE_UNVERIFIED", result)
        self.assertEqual(result["market_analysis"]["status"], "REPORTED_UNVERIFIED")
        self.assertIsNotNone(result["market_analysis"]["beta"])
        self.assertEqual(result["matched_observation_count"], 65)
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["source_rights_verified"])
        self.assertFalse(result["full_a_b_c_ready"])

    def test_hidden_without_license_and_approval_click(self):
        st = FakeSt(clicked=LABEL, values={
            "kuodra_p100_ticker": "NVDA", "kuodra_p100_as_of": "2026-02-01",
        }, uploads=make_inputs(), checks={"kuodra_p141_pair_ack": True})
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"},
                        clear=True), patch(
                "proofinvest.market_pair_engine_a.fetch_and_analyze_market_pair",
                side_effect=AssertionError("NO_VENDOR")) as vendor:
            ui.render_single_ticker_search(st)
        vendor.assert_not_called()
        self.assertTrue(any(name == LABEL and disabled for name, disabled in st.buttons))

    def test_single_explicit_market_pair_click_after_seven_stage_replay(self):
        class OwnerUi(FakeSt):
            session_state = {}
        st = OwnerUi(clicked=LABEL, values={
            "kuodra_p100_ticker": "NVDA", "kuodra_p100_as_of": "2026-02-01",
        }, uploads=make_inputs(), checks={"kuodra_p141_pair_ack": True})
        pair = {
            "status": "ENGINE_A_PRICE_INDEX_DESCRIPTIVE_UNVERIFIED",
            "market_analysis": {
                "security_return_pct": "12.5000", "benchmark_return_pct": "8.5000",
                "beta": "1.3000",
            },
            "matched_observation_count": 45,
            "stock_response_sha256": "a" * 64,
            "index_response_sha256": "b" * 64,
            "network_requests": 2,
        }
        with (patch.dict(os.environ, {**GATES, "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}),
              patch.object(transport, "_open_once",
                           side_effect=AssertionError("SEC HTTP NEVER")) as sec,
              patch("proofinvest.market_pair_engine_a.fetch_and_analyze_market_pair",
                    return_value=pair) as vendor):
            ui.render_single_ticker_search(st)
            # Second exact click in same session must not repeat vendor calls.
            ui.render_single_ticker_search(st)
        sec.assert_not_called()
        vendor.assert_called_once()
        self.assertEqual(vendor.call_args.kwargs["ticker"], "NVDA")
        self.assertEqual(vendor.call_args.kwargs["issuer_cik"], "0001045810")
        self.assertEqual(vendor.call_args.kwargs["as_of"], "2026-02-01")
        self.assertEqual(vendor.call_args.kwargs["api_key"], AV_KEY)
        self.assertTrue(any(k == "metric" and val[0] == "OLS 베타 (투자 추천 아님)"
                            and val[1] == "1.3000"
                            for k, val in st.messages))
        self.assertNotIn(AV_KEY, repr(st.messages))
        self.assertTrue(any(k == "warning" and "중복" in val
                            for k, val in st.messages))

    def test_invalid_source_never_triggers_premium_request(self):
        inputs = make_inputs()
        inputs["kuodra_p116_companyfacts"] = Uploaded(b"{}")
        st = FakeSt(clicked=LABEL, values={
            "kuodra_p100_ticker": "NVDA", "kuodra_p100_as_of": "2026-02-01",
        }, uploads=inputs, checks={"kuodra_p141_pair_ack": True})
        with (patch.dict(os.environ, {**GATES, "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}),
              patch("proofinvest.market_pair_engine_a.fetch_and_analyze_market_pair",
                    side_effect=AssertionError("NO_PREMIUM_IO")) as vendor):
            ui.render_single_ticker_search(st)
        vendor.assert_not_called()
        self.assertTrue(any(k == "warning" for k, _ in st.messages))


if __name__ == "__main__":
    unittest.main()
