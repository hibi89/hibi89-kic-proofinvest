"""P229: genuine real-issuer-linked offline NDX rights procurement preflight."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest

from proofinvest.real_issuer_ndx_license_gap import (
    build_issuer_ndx_license_gap, replay_issuer_ndx_license_gap,
)
MODE = "KUODRA · 실제 발행사 종목 직접 입력 (2종 · 제한)"


class RealIssuerNDXLicenseGapTests(unittest.TestCase):
    def test_all_provider_use_case_combinations_bound_to_real_issuer(self):
        providers=("massive", "twelve_data", "fred", "nasdaq_gids", "nasdaq_data_link")
        uses=("internal_research", "contest_judge_demo", "public_dashboard", "commercial_product")
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_VENDOR_NET")) as network:
            for ticker in ("NVDA", "DELL"):
                for vendor in providers:
                    for use in uses:
                        with self.subTest(ticker=ticker,vendor=vendor,use=use):
                            r=build_issuer_ndx_license_gap(
                                ticker=ticker,provider=vendor,intended_use=use)
                            self.assertEqual(
                                r["status"],"ISSUER_BOUND_NDX_LICENSE_GAPS_HUMAN_ONLY",r)
                            self.assertTrue(replay_issuer_ndx_license_gap(r))
                            self.assertEqual(r["ticker"],ticker)
                            self.assertEqual(r["instrument"],"NDX")
                            self.assertEqual(r["benchmark"],"NASDAQ_100")
                            self.assertEqual(len(r["historical_issuer_original_sha256"]),64)
                            self.assertTrue(r["vendor_terms_url"].startswith("https://"))
                            self.assertTrue(r["blocking_legal_scope_codes"])
                            self.assertFalse(r["request_execution_authorized"])
                            self.assertFalse(r["market_vendor_authenticated"])
                            self.assertFalse(r["market_index_ndx_identified_by_provider"])
                            self.assertFalse(r["licensed_stock_and_ndx_available"])
                            self.assertFalse(r["source_rights_verified"] if
                                             "source_rights_verified" in r else
                                             r["data_use_rights_verified"])
                            self.assertFalse(r["model_use_rights_verified"])
                            self.assertFalse(r["display_rights_verified"])
                            self.assertFalse(r["full_abc_complete"])
                            self.assertFalse(r["trade_executed"])
                            self.assertEqual(r["external_network_requests"],0)
                            self.assertEqual(r["guard_policy_preview"],"HOLD")
            network.assert_not_called()

    def test_illegal_provider_ticker_vintage_and_rights_promotion_blocked(self):
        for kw in (
            {"ticker":"AAPL","provider":"massive","intended_use":"internal_research"},
            {"ticker":"NVDA","provider":"qqq","intended_use":"internal_research"},
            {"ticker":"NVDA","provider":"fred","intended_use":"repackage_market_data"},
            {"ticker":"NVDA","provider":"massive","intended_use":"public_dashboard",
             "as_of":"2026-11-06"},
        ):
            with self.subTest(kw=kw):
                self.assertEqual(build_issuer_ndx_license_gap(**kw)["status"],"BLOCKED")
        with patch("proofinvest.real_issuer_ndx_license_gap.review_supported_real_ticker",
                   return_value={"status":"BLOCKED"}):
            self.assertEqual(build_issuer_ndx_license_gap(
                ticker="NVDA",provider="massive",
                intended_use="internal_research")["status"],"BLOCKED")
        with patch("proofinvest.real_issuer_ndx_license_gap.evaluate_provider",
                   return_value={"status":"GRANTED"}):
            self.assertEqual(build_issuer_ndx_license_gap(
                ticker="NVDA",provider="massive",
                intended_use="internal_research")["status"],"BLOCKED")

    def test_recomputed_sha_does_not_fake_a_licensed_market_source(self):
        r=build_issuer_ndx_license_gap(
            ticker="NVDA",provider="nasdaq_data_link",
            intended_use="contest_judge_demo")
        changed=deepcopy(r)
        changed["data_use_rights_verified"]=True
        self.assertFalse(replay_issuer_ndx_license_gap(changed))
        changed=deepcopy(r)
        changed["ticker"]="DELL"
        self.assertFalse(replay_issuer_ndx_license_gap(changed))
        changed=deepcopy(r)
        changed["market_index_ndx_identified_by_provider"]=True
        self.assertFalse(replay_issuer_ndx_license_gap(changed))
        self.assertNotIn("api_key",str(r).lower())
        self.assertNotIn("secret",str(r).lower())

    def test_native_streamlit_default_no_network_then_explicit_rights_click(self):
        from streamlit.testing.v1 import AppTest
        app=Path(__file__).resolve().parents[1]/"streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True),patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_NET")):
            at=AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(MODE).run(timeout=30)
            next(x for x in at.text_input if x.key=="p218_real_issuer_input").set_value(
                "NVDA").run(timeout=30)
            self.assertFalse(at.exception,[str(x.message) for x in at.exception])
            self.assertTrue(any("NDX 공급자 사용권" in x.value for x in at.subheader))
            self.assertFalse(any("NDX 공급자 실계정·이용권" in x.value
                                 for x in at.warning))
            next(x for x in at.button if x.key=="p229_ndx_rights_submit").click().run(timeout=30)
            self.assertFalse(at.exception,[str(x.message) for x in at.exception])
            self.assertTrue(any("NDX 공급자 실계정·이용권" in x.value
                                for x in at.warning))
            next(x for x in at.text_input if x.key=="p218_real_issuer_input").set_value(
                "AAPL").run(timeout=30)
            self.assertFalse(at.exception)
            self.assertFalse(any("NDX 공급자 사용권" in x.value for x in at.subheader))

    def test_issuer_chain_failure_cannot_render_download(self):
        from streamlit.testing.v1 import AppTest
        app=Path(__file__).resolve().parents[1]/"streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True), patch(
                   "proofinvest.real_issuer_ndx_license_gap.evaluate_provider",
                   return_value={"status":"GRANTED"}):
            at=AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(MODE).run(timeout=30)
            next(x for x in at.text_input if x.key=="p218_real_issuer_input").set_value(
                "DELL").run(timeout=30)
            next(x for x in at.button if x.key=="p229_ndx_rights_submit").click().run(timeout=30)
            self.assertFalse(at.exception)
            self.assertTrue(any("공급자 사용권 점검이 일치하지 않아 차단" in x.value
                                for x in at.warning))
            self.assertFalse(any(x.key=="p229_ndx_gap_export" for x in at.button))
