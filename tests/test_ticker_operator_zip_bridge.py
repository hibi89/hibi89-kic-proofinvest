"""P144 existing operator ZIP -> seven-step ticker workflow, zero external I/O."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import unittest
from unittest.mock import patch

from proofinvest.operator_sec_zip import make_operator_sec_zip_bytes
from proofinvest.ticker_operator_zip_bridge import restore_operator_zip_for_ticker
from proofinvest.ticker_local_workflow import run_local_ticker_workflow
from proofinvest import ticker_research_ui as ticker_ui
from tests.test_ticker_market_industry_bridge import scenario
from tests.test_ticker_research_ui import FakeSt, Uploaded


def fixture(*, symbol="NVDA", name="SYNTHETIC ISSUER", as_of="2026-02-01",
            accession="0001045810-25-000020", different_cik=False):
    _, raws, market, industry = scenario()
    sub = json.loads(raws["submissions"])
    sub["name"] = name
    sub["tickers"] = [symbol]
    if different_cik:
        sub["cik"] = 320193
    body = dict(raws)
    body["submissions"] = json.dumps(sub, sort_keys=True).encode("utf-8")
    archive = make_operator_sec_zip_bytes(
        submissions=body["submissions"],
        companyfacts=body["companyfacts"],
        original_filing=body["original_10k"],
        issuer_cik="0001045810", accession=accession,
        as_of=as_of, collected_at=as_of + "T12:00:00Z",
    )
    return archive, body, market, industry


class OperatorZipBridgeTests(unittest.TestCase):
    def test_single_zip_reaches_actual_seven_tool_report_and_guard(self):
        archive, originals, market, industry = fixture()
        market_json, industry_json = json.dumps(market).encode(), json.dumps(industry).encode()
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO HTTP")) as net:
            sources, receipt = restore_operator_zip_for_ticker(
                archive, ticker="NVDA", as_of="2026-02-01")
            workflow = run_local_ticker_workflow(
                ticker="NVDA", as_of="2026-02-01", sources=sources,
                market_json=market_json, industry_json=industry_json)
        net.assert_not_called()
        self.assertEqual(workflow["status"], "READY_FOR_HUMAN_REVIEW_UNVERIFIED", workflow)
        self.assertEqual(workflow["tool_calls_executed"], 7)
        self.assertEqual(workflow["supplementary"]["engine_c"]["status"],
                         "OBSERVED_COMPARISON_UNVERIFIED")
        self.assertEqual(workflow["original"]["guard_preview"]["decision"], "HOLD")
        self.assertEqual(workflow["receipt"]["source_sha256"]["companyfacts"],
                         receipt["source_sha256"]["companyfacts"])
        self.assertEqual(receipt["ticker_map_derivation"],
                         "SELF_REPORTED_SUBMISSIONS_TICKER_NOT_OFFICIAL_MAP")
        self.assertFalse(receipt["source_authenticated"])
        self.assertFalse(workflow["source_authenticated"])
        self.assertFalse(workflow["trade_executed"])

    def test_zip_only_real_streamlit_button_displays_and_downloads_report(self):
        archive, _, _, _ = fixture()
        st = FakeSt(
            clicked="로컬 원본으로 출처 계획 확인",
            values={"kuodra_p100_ticker": "NVDA", "kuodra_p100_as_of": "2026-02-01"},
            uploads={"kuodra_p144_operator_zip": Uploaded(archive)},
        )
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"},
                        clear=True), patch("urllib.request.urlopen",
                                          side_effect=AssertionError("NO HTTP")) as net:
            ticker_ui.render_single_ticker_search(st)
        net.assert_not_called()
        self.assertTrue(any(k == "download" and
                            x["file_name"] == "kuodra-local-four-source-UNVERIFIED.json"
                            for k, x in st.messages))
        self.assertTrue(any(k == "json" and isinstance(v, dict)
                            and v.get("status") == "LOCAL_OPERATOR_ZIP_DERIVED_TICKER_MAP_UNVERIFIED"
                            for k, v in st.messages))
        self.assertTrue(any(k == "warning" and "공식 SEC ticker_map" in v
                            for k, v in st.messages))
        self.assertFalse(any(k == "error" for k, _ in st.messages))

    def test_wrong_ticker_or_timestamp_blocks_without_partial_bytes(self):
        archive, *_ = fixture()
        for ticker, as_of in (("AAPL","2026-02-01"),
                              ("NVDA","2026-02-02"),
                              ("NVDA","2099-01-01"), ("../bad","2026-02-01")):
            with self.subTest(ticker=ticker, as_of=as_of):
                with self.assertRaises(ValueError):
                    restore_operator_zip_for_ticker(
                        archive, ticker=ticker, as_of=as_of)

    def test_missing_ticker_metadata_not_promoted_to_official_ticker_map(self):
        for symbol in ("AAPL", "NVDA "):
            archive, *_ = fixture(symbol=symbol)
            with self.assertRaises(ValueError):
                restore_operator_zip_for_ticker(
                    archive, ticker="NVDA", as_of="2026-02-01")

    def test_wrong_accession_cannot_enter_seven_step(self):
        archive, *_ = fixture(accession="0001045810-24-000010")
        with self.assertRaises(ValueError):
            restore_operator_zip_for_ticker(
                archive, ticker="NVDA", as_of="2026-02-01")

    def test_zip_and_four_individual_sources_cannot_mix(self):
        archive, raws, _, _ = fixture()
        st = FakeSt(clicked="로컬 원본으로 출처 계획 확인",
                    values={"kuodra_p100_ticker": "NVDA",
                            "kuodra_p100_as_of": "2026-02-01"},
                    uploads={"kuodra_p144_operator_zip": Uploaded(archive),
                             "kuodra_p100_ticker_map": Uploaded(b"{}")})
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"},
                        clear=True):
            ticker_ui.render_single_ticker_search(st)
        self.assertTrue(any(kind == "warning" and "동시에" in value
                            for kind, value in st.messages))
        self.assertFalse(any(kind == "download" for kind, _ in st.messages))

    def test_tampered_archive_rejected_by_existing_zip_reader(self):
        archive, *_ = fixture()
        bad = bytearray(archive)
        marker = archive.index(b"kuodra.operator-three-sec-source-zip.v1")
        bad[marker + 3] ^= 1
        with self.assertRaises(ValueError):
            restore_operator_zip_for_ticker(
                bytes(bad), ticker="NVDA", as_of="2026-02-01")

    def test_local_record_identity_only_no_api_keys_or_raw_in_receipt(self):
        archive, *_ = fixture()
        _, receipt = restore_operator_zip_for_ticker(
            archive, ticker="NVDA", as_of="2026-02-01")
        data = json.dumps(receipt)
        self.assertNotIn("<html", data.lower())
        self.assertNotIn("SYNTHETIC ISSUER", data)
        self.assertNotIn("source_data", data)
        self.assertFalse(receipt["source_rights_verified"])
        self.assertFalse(receipt["independent_ticker_registry_verified"])
        self.assertFalse(receipt["external_http_attempted"])


if __name__ == "__main__":
    unittest.main()
