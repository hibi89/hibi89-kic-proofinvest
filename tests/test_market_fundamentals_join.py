"""P271 integration: source, time, ticker and Guard fail-closed join."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from proofinvest.market_panel_review import review_local_market_panel
from proofinvest.market_fundamentals_join import (
    build_local_panel_fundamentals_join,
    verify_local_panel_fundamentals_join,
)
from tests.test_market_panel_offline import raw


def case(*, count=3, bars=92, as_of="2026-11-05"):
    symbols=["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL"][:count]
    sources={s:raw(s,count=bars) for s in ("I:NDX",*symbols)}
    filing_dates={s:"2026-07-31" for s in symbols}
    market=review_local_market_panel(
        sources,symbols,filing_dates,as_of=as_of)
    assert market["status"]=="MULTI_ISSUER_ENGINE_A_DESCRIPTIVE_UNVERIFIED", market
    return market,sources,symbols,filing_dates


class MarketFundamentalsJoinTests(unittest.TestCase):
    def join(self, fixture, *, as_of="2026-11-05"):
        return build_local_panel_fundamentals_join(*fixture,as_of=as_of)

    def test_three_and_five_stock_nvda_b_c_replay(self):
        for count in (3,5):
            with self.subTest(count=count):
                data=case(count=count)
                with patch("urllib.request.urlopen",
                           side_effect=AssertionError("NO_NETWORK")) as network:
                    result=self.join(data)
                    self.assertTrue(verify_local_panel_fundamentals_join(
                        result,*data,as_of="2026-11-05"),result)
                network.assert_not_called()
                self.assertEqual(result["status"],
                    "LOCAL_MARKET_AND_NVDA_B_C_REVIEW_UNVERIFIED")
                self.assertEqual(result["bc_issuer_count"],1)
                self.assertEqual(result["issuer_count"],count)
                nvda=result["issuers"][0]
                self.assertEqual(nvda["ticker"],"NVDA")
                self.assertEqual(nvda["issuer_cik"],"0001045810")
                self.assertEqual(nvda["engine_b"]["revenue_growth_pct"],"65.47")
                self.assertEqual([p["ticker"] for p in nvda["engine_c"]["peers"]],
                                 ["AMD","INTC"])
                self.assertEqual(nvda["guard_decision"],"HOLD")
                self.assertFalse(nvda["market_fundamental_causal_alignment_verified"])
                for item in result["issuers"][1:]:
                    self.assertIsNone(item["engine_b"])
                    self.assertIsNone(item["engine_c"])
                    self.assertEqual(item["bc_status"],
                        "UNAVAILABLE_NO_PINNED_FIRST_PARTY_B_C_FOR_ISSUER")
                for flag in ("full_abc_complete","source_rights_verified",
                             "public_display_allowed","trade_executed",
                             "market_fundamental_causal_alignment_verified"):
                    self.assertIs(result[flag],False,flag)
                self.assertEqual(result["market_api_requests"],0)
                self.assertEqual(result["llm_requests"],0)

    def test_bc_vintage_cannot_time_travel(self):
        old=case(bars=65,as_of="2026-10-01")
        result=self.join(old,as_of="2026-10-01")
        self.assertTrue(verify_local_panel_fundamentals_join(
            result,*old,as_of="2026-10-01"))
        self.assertEqual(result["bc_issuer_count"],0)
        self.assertEqual(result["issuers"][0]["bc_status"],
                         "UNAVAILABLE_B_C_REVIEW_AFTER_MARKET_ASOF")
        stale=case(bars=65,as_of="2026-11-05")
        stale_result=self.join(stale)
        self.assertTrue(verify_local_panel_fundamentals_join(
            stale_result,*stale,as_of="2026-11-05"))
        self.assertEqual(stale_result["bc_issuer_count"],0)
        self.assertEqual(stale_result["issuers"][0]["bc_status"],
                         "UNAVAILABLE_MARKET_END_BEFORE_B_C_REVIEW")

    def test_modified_market_bytes_or_identifiers_or_hash_rejected(self):
        data=case()
        valid=self.join(data)
        self.assertTrue(verify_local_panel_fundamentals_join(
            valid,*data,as_of="2026-11-05"))
        modified=deepcopy(valid)
        modified["issuers"][0]["engine_b"]["revenue_growth_pct"]="999"
        self.assertFalse(verify_local_panel_fundamentals_join(
            modified,*data,as_of="2026-11-05"))
        new_sources=dict(data[1]);new_sources["NVDA"]=raw("NVDA",count=92,bump=2)
        self.assertFalse(verify_local_panel_fundamentals_join(
            valid,data[0],new_sources,data[2],data[3],as_of="2026-11-05"))
        wrong_market=deepcopy(data[0])
        wrong_market["issuers"][0]["issuer_cik"]="0000320193"
        self.assertEqual(build_local_panel_fundamentals_join(
            wrong_market,*data[1:],as_of="2026-11-05")["status"],"BLOCKED")
        promoted=deepcopy(valid)
        promoted["public_display_allowed"]=True
        self.assertFalse(verify_local_panel_fundamentals_join(
            promoted,*data,as_of="2026-11-05"))

    def test_missing_original_b_or_bad_guard_blocks_join(self):
        data=case()
        with patch("proofinvest.market_fundamentals_join.build_marketless_global_review",
                   return_value={"status":"BLOCKED"}):
            r=self.join(data)
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(r["guard_decision"],"HOLD")
        self.assertFalse(r["source_rights_verified"])
        self.assertFalse(verify_local_panel_fundamentals_join(
            r,*data,as_of="2026-11-05"))

if __name__=="__main__":
    unittest.main()
