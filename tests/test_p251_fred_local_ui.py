"""P251 KUODRA local FRED NASDAQ100 UI, real Decimal A, 0 network.

No real owner file, provider key, dataset, SEC original or commercial right
is bundled into tests. Only strictly synthetic local CSV.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from proofinvest import ticker_research_ui as ui
from tests.test_ticker_research_ui import FakeSt, Uploaded
from tests.test_fred_nasdaq100_offline import fred_data, stock_data, AS_OF, FILING, CIK

LABEL = "FRED 공식 Nasdaq-100 CSV 오프라인 확인·Engine A 계산"
ENV = {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}


def make_st(*, index=None, stock=None, clicked=LABEL, ack=True,
            ticker="AAPL", as_of=AS_OF, cik=CIK, filing=FILING,
            source="https://example.org/market-data"):
    uploads = {}
    if index is not None:
        uploads["kuodra_p251_fred_index"] = Uploaded(index)
    if stock is not None:
        uploads["kuodra_p251_fred_stock"] = Uploaded(stock)
    return FakeSt(
        clicked=clicked,
        values={
            "kuodra_p100_ticker": ticker,
            "kuodra_p100_as_of": as_of,
            "kuodra_p251_fred_cik": cik,
            "kuodra_p251_fred_filing": filing,
            "kuodra_p251_fred_stock_url": source,
        },
        checks={"kuodra_p251_fred_ack":ack},
        uploads=uploads,
    )


def outputs(st, status):
    return [v for k, v in st.messages if k == "json"
            and type(v) is dict and v.get("status") == status]


class FredLocalResearchUiTests(unittest.TestCase):
    def test_disabled_without_ack_no_network(self):
        st=make_st(index=fred_data(),stock=stock_data(),ack=False)
        with patch.dict(os.environ, ENV, clear=True), (
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("OUTBOUND HTTP"))), (
            patch("proofinvest.fred_nasdaq100_offline.parse_fred_nasdaq100_csv",
                  side_effect=AssertionError("NO READ BEFORE CLICK"))):
            ui.render_single_ticker_search(st)
        self.assertEqual([d for label,d in st.buttons if label==LABEL],[True])
        self.assertFalse(outputs(st,"LOCAL_FRED_CSV_PARSED_ORIGIN_UNVERIFIED"))

    def test_disabled_without_index_even_with_stock_and_ack(self):
        st=make_st(stock=stock_data())
        with patch.dict(os.environ,ENV,clear=True):
            ui.render_single_ticker_search(st)
        self.assertEqual([d for label,d in st.buttons if label==LABEL],[True])

    def test_fred_only_on_click_no_stock_or_external_network(self):
        st=make_st(index=fred_data())
        with patch.dict(os.environ,ENV,clear=True), (
            patch("urllib.request.urlopen",side_effect=AssertionError("HTTP"))), (
            patch("proofinvest.market_provider_massive.fetch_massive_pair",
                  side_effect=AssertionError("MASSIVE"))):
            ui.render_single_ticker_search(st)
        results=outputs(st,"LOCAL_FRED_CSV_PARSED_ORIGIN_UNVERIFIED")
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]["index_points"],65)
        self.assertEqual(results[0]["index_symbol"],"I:NDX")
        self.assertFalse(results[0]["source_authenticated"])
        self.assertFalse(results[0]["commercial_reuse_allowed"])
        self.assertFalse(results[0]["ai_processing_allowed"])
        self.assertEqual(results[0]["network_requests"],0)
        self.assertNotIn("close_observations",repr(st.messages))
        self.assertFalse(any(k=="download" for k,_ in st.messages))

    def test_local_stock_plus_fred_decimal_engine_a_real_computation(self):
        st=make_st(index=fred_data(),stock=stock_data())
        with patch.dict(os.environ,ENV,clear=True), (
            patch("urllib.request.urlopen",side_effect=AssertionError("HTTP"))):
            ui.render_single_ticker_search(st)
        results=outputs(st,"OFFLINE_FRED_ENGINE_A_DESCRIPTIVE_UNVERIFIED")
        self.assertEqual(len(results),1)
        result=results[0]
        self.assertEqual(result["matched_observation_count"],42)
        self.assertEqual(result["matched_period_start"],"2026-08-03")
        self.assertEqual(result["matched_period_end"],"2026-09-29")
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["full_a_b_c_ready"])
        metrics=[v for k,v in st.messages if k=="metric"
                 and v[0]=="로컬 Engine A 베타 (공급자 미인증)"]
        self.assertEqual(len(metrics),1)
        self.assertNotEqual(metrics[0][1],"산출 불가")
        self.assertEqual(result["network_requests"],0)
        self.assertNotIn("close_observations",repr(st.messages))

    def test_invalid_benchmark_qqq_cannot_be_displayed_as_ndx(self):
        bad=fred_data().replace(b"NASDAQ100",b"QQQ",1)
        st=make_st(index=bad)
        with patch.dict(os.environ,ENV,clear=True):
            ui.render_single_ticker_search(st)
        self.assertTrue(any(k=="code" and v=="P251_LOCAL_SOURCE_INVALID_OR_UNAVAILABLE"
                            for k,v in st.messages))
        self.assertFalse(any(k=="metric" and v[0].startswith("로컬 Engine")
                             for k,v in st.messages))
        self.assertFalse(outputs(st,"LOCAL_FRED_CSV_PARSED_ORIGIN_UNVERIFIED"))

    def test_filing_calendar_failure_never_promotes_pair_or_persists(self):
        st=make_st(index=fred_data(),stock=stock_data(),
                   filing="2026-09-01")
        with patch.dict(os.environ,ENV,clear=True):
            ui.render_single_ticker_search(st)
        self.assertEqual(len(outputs(st,"PAIR_BLOCKED")),1)
        self.assertFalse(outputs(st,"OFFLINE_FRED_ENGINE_A_DESCRIPTIVE_UNVERIFIED"))
        self.assertFalse(any(k=="download" for k,_ in st.messages))

    def test_invalid_oversized_upload_fails_closed_no_response_echo(self):
        st=make_st(index=b"observation_date,NASDAQ100\n" + b"x"*2097152)
        with patch.dict(os.environ,ENV,clear=True):
            ui.render_single_ticker_search(st)
        self.assertTrue(any(k=="code" and v=="P251_LOCAL_SOURCE_INVALID_OR_UNAVAILABLE"
                            for k,v in st.messages))
        self.assertNotIn("xxxxx",repr(st.messages))

    def test_existing_sec_primary_button_stays_first(self):
        st=make_st(index=fred_data(),clicked="NO_BUTTON")
        with patch.dict(os.environ,ENV,clear=True):
            ui.render_single_ticker_search(st)
        self.assertEqual(st.buttons[0][0],"SEC 원문 4종 자동 수집 실행")
        self.assertTrue(any(x[0]==LABEL for x in st.buttons))

    def test_public_binding_or_no_owner_gate_rejects_panel_completely(self):
        for addr, env in (("0.0.0.0",ENV),("127.0.0.1",{})):
            st=FakeSt(addr,clicked=LABEL,uploads={
                "kuodra_p251_fred_index":Uploaded(fred_data())},
                checks={"kuodra_p251_fred_ack":True})
            with self.subTest(addr=addr),patch.dict(os.environ,env,clear=True),(
                patch("urllib.request.urlopen",side_effect=AssertionError("HTTP"))):
                ui.render_single_ticker_search(st)
            self.assertFalse(any(b[0]==LABEL for b in st.buttons))


if __name__=="__main__":
    unittest.main()
