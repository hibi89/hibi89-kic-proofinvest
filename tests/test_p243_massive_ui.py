"""Massive Personal Basic P243 UI: does not trigger HTTP on rerun or disabled."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from proofinvest import ticker_research_ui as ui
from tests.test_p141_market_pair_integration import make_inputs
from tests.test_ticker_research_ui import FakeSt

LABEL = "Massive 무료 플랜 · 로컬 SEC 검산 후 주가+NDX 분석 (최대 2회)"
GATES = {
    "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
    "KUODRA_ENABLE_MASSIVE_PAIR": "1",
    "KUODRA_MASSIVE_PERSONAL_RESEARCH_APPROVED": "1",
    "MASSIVE_API_KEY": "SYNTHETICLOCALKEYONLY123",
}


class MassiveResearchUiTests(unittest.TestCase):
    def test_free_basic_today_button_disabled_even_with_owner_gates(self):
        st = FakeSt(clicked=LABEL, values={
            "kuodra_p100_ticker": "NVDA",
            "kuodra_p100_as_of": "2026-02-01",
        }, uploads=make_inputs(), checks={"kuodra_p243_massive_ack": True})
        with patch.dict(os.environ,GATES,clear=True), (
            patch("proofinvest.market_provider_massive.free_basic_safe_as_of",
                  return_value="2026-01-31")), (
            patch("proofinvest.market_provider_massive.fetch_massive_pair",
                  side_effect=AssertionError("NO PROVIDER HTTP"))):
            ui.render_single_ticker_search(st)
        self.assertTrue(any(label==LABEL and disabled for label,disabled in st.buttons))

    def test_missing_personal_license_gate_disables_button(self):
        st = FakeSt(clicked=LABEL, values={
            "kuodra_p100_ticker": "NVDA", "kuodra_p100_as_of": "2026-02-01",
        }, uploads=make_inputs(), checks={"kuodra_p243_massive_ack": True})
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"},
                        clear=True), patch(
            "proofinvest.market_provider_massive.fetch_massive_pair",
            side_effect=AssertionError("NO MASSIVE NETWORK"),
        ) as vendor:
            ui.render_single_ticker_search(st)
        vendor.assert_not_called()
        self.assertTrue(any(k == LABEL and disabled for k, disabled in st.buttons))

    def test_authorized_click_after_local_sec_replay_only_once(self):
        class St(FakeSt):
            session_state = {}
        st = St(clicked=LABEL, values={
            "kuodra_p100_ticker": "NVDA", "kuodra_p100_as_of": "2026-02-01",
        }, uploads=make_inputs(), checks={"kuodra_p243_massive_ack": True})
        result = {
            "status": "ENGINE_A_MASSIVE_DESCRIPTIVE_UNVERIFIED",
            "reason_code": "PROVIDER_RIGHTS_AND_ORIGIN_UNVERIFIED",
            "market_analysis": {"beta": "1.2345", "status": "REPORTED_UNVERIFIED"},
            "matched_observation_count": 42,
            "matched_period_start": "2025-11-10",
            "matched_period_end": "2026-01-31",
            "stock_response_sha256": "a" * 64,
            "index_response_sha256": "b" * 64,
            "network_requests": 2,
            "source_authenticated": False, "source_rights_verified": False,
            "trade_executed": False,
        }
        with patch.dict(os.environ,GATES,clear=True), patch(
            "proofinvest.market_provider_massive.fetch_massive_pair", return_value=result,
        ) as provider:
            ui.render_single_ticker_search(st)
            ui.render_single_ticker_search(st)
        provider.assert_called_once()
        self.assertEqual(provider.call_args.kwargs["ticker"], "NVDA")
        self.assertEqual(provider.call_args.kwargs["issuer_cik"], "0001045810")
        self.assertEqual(provider.call_args.kwargs["api_key"], GATES["MASSIVE_API_KEY"])
        self.assertTrue(any(k=="metric" and v[0]=="개인 로컬 Engine A 베타 (미인증)"
                            and v[1]=="1.2345" for k,v in st.messages))
        self.assertTrue(any(k=="warning" and "중복" in v for k,v in st.messages))
        self.assertNotIn(GATES["MASSIVE_API_KEY"],repr(st.messages))

    def test_corrupt_session_duplicate_ledger_blocks_without_http(self):
        class St(FakeSt):
            session_state = {"kuodra_p155_pair_attempt_history": ["CORRUPTED"]}
        st = St(clicked=LABEL, values={
            "kuodra_p100_ticker": "NVDA", "kuodra_p100_as_of": "2026-02-01",
        }, uploads=make_inputs(), checks={"kuodra_p243_massive_ack": True})
        with patch.dict(os.environ,GATES,clear=True), patch(
            "proofinvest.market_provider_massive.fetch_massive_pair",
            side_effect=AssertionError("SHOULD NOT EXECUTE")
        ) as vendor:
            ui.render_single_ticker_search(st)
        vendor.assert_not_called()
        self.assertTrue(any(k == "warning" and "장부 오류" in v
                            for k,v in st.messages))

if __name__=="__main__":
    unittest.main()
