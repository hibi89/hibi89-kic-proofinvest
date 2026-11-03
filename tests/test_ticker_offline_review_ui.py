"""P167 real local first-packet UI, zero network and no Premium approval."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from proofinvest import ticker_research_ui as ui
from proofinvest.ticker_review_packet import inspect_review_packet_bytes
from tests.test_ticker_market_pair_evidence import _prepared, _body
from tests.test_ticker_research_ui import FakeSt, Uploaded

_BUTTON = "로컬 SEC + 종목·실제 NDX A/B/C 통합 검토 파일 생성 (외부 요청 0회)"
_DOWNLOAD = "로컬 A/B/C 검토 패키지 JSON 다운로드 (미인증)"


def ui_inputs():
    _workflow, originals, market, industry, _stock, _index = _prepared()
    return {
        "kuodra_p100_ticker_map": Uploaded(originals["ticker_map"]),
        "kuodra_p100_submissions": Uploaded(originals["submissions"]),
        "kuodra_p116_companyfacts": Uploaded(originals["companyfacts"]),
        "kuodra_p116_original": Uploaded(originals["original_10k"]),
        "kuodra_p104_market_json": Uploaded(market),
        "kuodra_p104_industry_json": Uploaded(industry),
        "kuodra_p167_stock": Uploaded(_body("NVDA")),
        "kuodra_p167_ndx": Uploaded(_body("NDX", 10000)),
    }


def render(uploads, *, clicked=_BUTTON, ack=True):
    st = FakeSt(
        clicked=clicked,
        values={"kuodra_p100_ticker": "NVDA",
                "kuodra_p100_as_of": "2026-02-01"},
        checks={"kuodra_p167_ack": ack},
        uploads=uploads,
    )
    with (
        patch.dict(os.environ, {
            "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
            "KUODRA_ENABLE_SEC_FETCH_UI": "0",
            "KUODRA_ENABLE_ALPHA_VANTAGE_DAILY": "0",
            "KUODRA_ENABLE_ALPHA_VANTAGE_INDEX": "0",
            "KUODRA_ALPHA_VANTAGE_INDEX_PREMIUM_APPROVED": "0",
            "KUODRA_ALPHA_VANTAGE_RIGHTS_APPROVED": "0",
        }, clear=True),
        patch("proofinvest.ticker_sec_transport._open_once",
              side_effect=AssertionError("NO_SEC_HTTP")) as sec,
        patch("proofinvest.market_pair_engine_a.fetch_and_analyze_market_pair",
              side_effect=AssertionError("NO_PAID_PROVIDER")) as provider,
        patch("urllib.request.urlopen",
              side_effect=AssertionError("NO_VENDOR_HTTP")) as net,
    ):
        ui.render_single_ticker_search(st)
    sec.assert_not_called()
    provider.assert_not_called()
    net.assert_not_called()
    return st


class InitialOfflineReviewUiTests(unittest.TestCase):
    def test_first_packet_created_without_vendor_credentials_and_downloads_safely(self):
        st = render(ui_inputs())
        downloads = [v for k, v in st.messages if k == "download"
                     and v["label"] == _DOWNLOAD]
        self.assertEqual(len(downloads), 1, st.messages)
        self.assertEqual(downloads[0]["file_name"],
                         "kuodra-offline-a-b-c-review-UNVERIFIED.json")
        self.assertEqual(inspect_review_packet_bytes(
            downloads[0]["data"])["status"],
            "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED")
        self.assertNotIn("close_observations", repr(downloads))
        self.assertNotIn("<html", repr(downloads).lower())
        outputs = [v for k, v in st.messages if k == "json"
                   and type(v) is dict and
                   v.get("market_math_recomputed") is True]
        self.assertEqual(len(outputs), 1, st.messages)
        self.assertEqual(outputs[0]["ticker"], "NVDA")
        self.assertEqual(outputs[0]["matched_sessions"], 65)
        self.assertEqual(outputs[0]["guard_policy_preview"], "HOLD")
        self.assertIs(outputs[0]["source_rights_verified"], False)
        self.assertEqual(outputs[0]["network_requests"], 0)

    def test_wrong_ndx_response_disables_download_and_does_not_call_provider(self):
        uploads = ui_inputs()
        uploads["kuodra_p167_ndx"] = Uploaded(_body("SPX", 10000))
        st = render(uploads)
        self.assertFalse(any(
            k == "download" and v["label"] == _DOWNLOAD
            for k, v in st.messages))
        self.assertTrue(any(
            k == "code" and v == "INVALID_SOURCE_OR_MARKET_RESPONSE"
            for k, v in st.messages), st.messages)

    def test_no_click_or_no_consent_blocks_analysis(self):
        for kwargs in ({"clicked": None}, {"ack": False}):
            with self.subTest(kwargs=kwargs), patch(
                "proofinvest.ticker_offline_review_builder.build_offline_initial_review",
                side_effect=AssertionError("NO_PASSIVE_SOURCE_REPLAY"),
            ) as builder:
                st = render(ui_inputs(), **kwargs)
                builder.assert_not_called()
                self.assertFalse(any(
                    k == "download" and v["label"] == _DOWNLOAD
                    for k, v in st.messages))


if __name__ == "__main__":
    unittest.main()
