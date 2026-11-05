"""P146 one-peer optional licensed vendor route, all HTTP mocked."""
from __future__ import annotations

from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch

from proofinvest.ticker_provider_sec_api import (
    _vendor_http, run_sec_api_on_demand, encode_vendor_evidence_json,
)
from proofinvest.ticker_vendor_peer import (
    choose_one_peer, extract_target_industry, industry_mapping_url,
)
from proofinvest.ticker_research_ui import render_single_ticker_search
from tests.test_ticker_provider_sec_api import vendor_responses, fake_call, _KEY, _GATES
from tests.test_ticker_research_ui import FakeSt


_PEER_ENV = {**_GATES, "KUODRA_ENABLE_SEC_API_PEER_EXTRA": "1",
             "KUODRA_SEC_API_PEER_RIGHTS_APPROVED": "1"}


def peer_responses():
    originals = vendor_responses()
    target = json.loads(originals[0])
    target[0].update(
        industry="Semiconductors", sector="Technology",
        category="Domestic Common Stock", currency="USD",
        isDelisted=False,
    )
    originals[0] = json.dumps(target).encode()
    peer = {"cik": "320193", "ticker": "AAPL",
            "industry": "Semiconductors", "sector": "Technology",
            "category": "Domestic Common Stock", "currency": "USD",
            "isDelisted": False}
    industry = json.dumps([peer, target[0]]).encode()
    filing = {"filings": [{
        "formType": "10-K", "accessionNo": "0000320193-25-000020",
        "cik": "320193", "ticker": "AAPL",
        "filedAt": "2025-10-15T10:00:00-04:00",
        "periodOfReport": "2025-09-30",
        "linkToFilingDetails": (
            "https://www.sec.gov/Archives/edgar/data/320193/"
            "000032019325000020/apple2025.htm"),
    }]}
    rows = [
        {"value": "150", "unitRef": "usd",
         "period": {"startDate": "2024-10-01", "endDate": "2025-09-30"}},
        {"value": "100", "unitRef": "usd",
         "period": {"startDate": "2023-10-01", "endDate": "2024-09-30"}},
    ]
    xbrl = {"CoverPage": {
        "DocumentType": "10-K", "DocumentPeriodEndDate": "2025-09-30",
        "EntityCentralIndexKey": "0000320193",
    }, "StatementsOfIncome": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": rows,
    }}
    return originals + [industry, json.dumps(filing).encode(),
                        json.dumps(xbrl).encode()]


def run_peer(*, responses=None, env=None, **changes):
    raw = responses if responses is not None else peer_responses()
    calls = []
    args = {
        "ticker": "NVDA", "as_of": "2026-02-01",
        "api_key": _KEY, "explicit_click": True,
        "operator_retrieval_approved": True,
        "operator_rights_approved": True,
        "include_one_peer": True, "peer_approved": True,
        "transport": fake_call(raw, calls),
    }
    args.update(changes)
    with patch.dict(os.environ, env if env is not None else _PEER_ENV, clear=True):
        result = run_sec_api_on_demand(**args)
    return result, calls


class P146PeerContractTests(unittest.TestCase):
    def test_7_requests_real_same_year_peer_join_and_report(self):
        r, calls = run_peer()
        self.assertEqual(r["status"], "SOURCE_REPLAYED_UNVERIFIED", r)
        self.assertEqual(r["provider_http_requests_attempted"], 7)
        self.assertEqual([row[0] for row in calls],
                         ["GET", "POST", "GET", "GET", "GET", "POST", "GET"])
        self.assertIn("/mapping/industry/Semiconductors", calls[4][1])
        p = r["peer_comparison"]
        self.assertEqual(p["status"], "PEER_ONE_PERIOD_ALIGNED_UNVERIFIED", p)
        self.assertEqual(p["peer_ticker"], "AAPL")
        self.assertEqual(p["prior_period_end"], "2024-09-30")
        self.assertEqual(p["current_period_end"], "2025-09-30")
        self.assertEqual(p["target_growth_pct"], "100.00")
        self.assertEqual(p["peer_growth_pct"], "50.00")
        self.assertEqual(p["growth_gap_to_one_peer_pp"], "50.00")
        self.assertFalse(p["source_authenticated"])
        self.assertFalse(p["full_engine_c_ready"])
        self.assertEqual(p["industry_series_status"], "UNAVAILABLE")
        self.assertEqual(r["report"]["guard_policy_preview"], "HOLD")
        self.assertFalse(r["trade_executed"])
        self.assertNotIn(_KEY, json.dumps(r))
        exported = json.loads(encode_vendor_evidence_json(r))
        self.assertEqual(exported["one_peer_partial_comparison"]["peer_ticker"], "AAPL")
        self.assertFalse(exported["source_rights_verified"])

    def test_four_call_old_path_still_works_and_does_not_fetch_peers(self):
        raw = peer_responses()
        calls = []
        args = dict(ticker="NVDA", as_of="2026-02-01", api_key=_KEY,
                    explicit_click=True, operator_retrieval_approved=True,
                    operator_rights_approved=True,
                    transport=fake_call(raw, calls))
        with patch.dict(os.environ, _GATES, clear=True):
            r = run_sec_api_on_demand(**args)
        self.assertEqual(r["status"], "SOURCE_REPLAYED_UNVERIFIED", r)
        self.assertEqual(r["provider_http_requests_attempted"], 4)
        self.assertNotIn("peer_comparison", r)
        self.assertEqual(len(calls), 4)
        self.assertNotIn("one_peer_partial_comparison",
                         json.loads(encode_vendor_evidence_json(r)))

    def test_missing_separate_peer_approval_blocks_before_one_network_attempt(self):
        for changes in ({"peer_approved": False},
                        {"include_one_peer": True, "peer_approved": True}):
            env = _PEER_ENV if changes["peer_approved"] is False else _GATES
            r, calls = run_peer(
                env=env, transport=lambda *_: self.fail("UNAUTHORIZED_NETWORK"),
                **changes)
            self.assertEqual(r["status"], "BLOCKED")
            self.assertEqual(r["provider_http_requests_attempted"], 0)
            self.assertEqual(calls, [])

    def test_mismatched_peer_fiscal_period_never_fabricates_comparison(self):
        raw = peer_responses()
        q = json.loads(raw[5]); row = q["filings"][0]
        row["periodOfReport"] = "2025-06-30"
        raw[5] = json.dumps(q).encode()
        r, calls = run_peer(responses=raw)
        self.assertEqual(r["status"], "SOURCE_REPLAYED_UNVERIFIED", r)
        self.assertEqual(r["provider_http_requests_attempted"], 6)
        self.assertEqual(r["peer_comparison"]["status"], "UNAVAILABLE")
        self.assertIsNone(r["peer_comparison"].get("growth_gap_to_one_peer_pp"))
        self.assertEqual(r["report"]["guard_policy_preview"], "HOLD")

    def test_xbrl_peer_cik_conflict_rejected_and_main_report_preserved(self):
        raw = peer_responses()
        xbrl = json.loads(raw[6])
        xbrl["CoverPage"]["EntityCentralIndexKey"] = "0001045810"
        raw[6] = json.dumps(xbrl).encode()
        r, calls = run_peer(responses=raw)
        self.assertEqual(r["status"], "SOURCE_REPLAYED_UNVERIFIED")
        self.assertEqual(r["provider_http_requests_attempted"], 7)
        self.assertEqual(r["peer_comparison"]["status"], "UNAVAILABLE")
        self.assertFalse(r["full_a_b_c_ready"])

    def test_same_issuer_different_ticker_never_selected_as_peer(self):
        raw = peer_responses()
        industry = json.loads(raw[4])
        industry[0]["cik"] = "1045810"
        raw[4] = json.dumps(industry).encode()
        r, calls = run_peer(responses=raw)
        self.assertEqual(r["provider_http_requests_attempted"], 5)
        self.assertEqual(r["peer_comparison"]["status"], "UNAVAILABLE")

    def test_one_peer_is_not_cohort_and_ambiguity_fails_closed(self):
        raw = json.dumps([
            {"cik": "320193", "ticker": "AAPL",
             "industry": "Semiconductors", "currency": "USD",
             "category": "Domestic Common Stock", "isDelisted": False},
            {"cik": "320193", "ticker": "APPLE",
             "industry": "Semiconductors", "currency": "USD",
             "category": "Domestic Common Stock", "isDelisted": False},
        ]).encode()
        with self.assertRaises(ValueError):
            choose_one_peer(raw, target_cik="0001045810",
                            target_ticker="NVDA", industry="Semiconductors")

    def test_query_http_has_required_json_content_type_and_no_real_socket(self):
        class Response:
            status = 200
            headers = {}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return "https://api.sec-api.io"
            def read(self, limit):
                return b'{"filings":[]}'
        checks = []
        class Opener:
            def open(self, request, timeout):
                checks.append((request.get_method(),
                               request.get_header("Content-type"),
                               request.get_header("Authorization"), timeout))
                return Response()
        with patch("proofinvest.ticker_provider_sec_api.build_opener",
                   return_value=Opener()) as stub:
            out = _vendor_http("POST", "https://api.sec-api.io",
                               b'{"query":"cik:320193"}', _KEY, 400000)
        stub.assert_called_once()
        self.assertEqual(checks, [("POST", "application/json", _KEY, 8)])
        self.assertEqual(out, b'{"filings":[]}')
        with self.assertRaises(ValueError):
            _vendor_http("GET", "https://api.sec-api.io/path",
                         b"unexpected", _KEY, 50)

    def test_ui_seven_call_button_with_separate_ack_and_export(self):
        result, calls = run_peer()
        self.assertEqual(result["peer_comparison"]["status"],
                         "PEER_ONE_PERIOD_ALIGNED_UNVERIFIED")
        label = "승인된 공급자 + 동종기업 1개 연간 매출 비교 (최대 7회)"
        st = FakeSt(
            clicked=label,
            values={"kuodra_p100_ticker": "NVDA",
                    "kuodra_p100_as_of": "2026-02-01"},
            checks={"kuodra_p145_vendor_ack": True,
                    "kuodra_p146_peer_ack": True},
        )
        env = {**_PEER_ENV, "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
               "KUODRA_SEC_API_VENDOR_KEY": _KEY}
        with patch.dict(os.environ, env, clear=True), patch(
            "proofinvest.ticker_provider_sec_api.run_sec_api_on_demand",
            return_value=result,
        ) as vendor:
            render_single_ticker_search(st)
        vendor.assert_called_once()
        self.assertTrue(vendor.call_args.kwargs["include_one_peer"])
        exports = [v for k,v in st.messages if k=="download" and
                   v["file_name"] == "kuodra-vendor-local-review-UNVERIFIED.json"]
        self.assertEqual(len(exports),1)
        payload=json.loads(exports[0]["data"])
        self.assertTrue(payload["one_peer_partial_comparison"]["single_peer_not_industry_cohort"])
        self.assertFalse(payload["one_peer_partial_comparison"]["full_engine_c_ready"])
        self.assertNotIn(_KEY,str(st.messages))

    def test_ui_peer_option_without_approval_disabled_no_network(self):
        label = "승인된 공급자 + 동종기업 1개 연간 매출 비교 (최대 7회)"
        st = FakeSt(clicked=label, checks={
            "kuodra_p145_vendor_ack": True, "kuodra_p146_peer_ack": True,
        })
        env={**_GATES,"KUODRA_ENABLE_LOCAL_SOURCE_UI":"1",
             "KUODRA_SEC_API_VENDOR_KEY":_KEY}
        with patch.dict(os.environ,env,clear=True),patch(
            "proofinvest.ticker_provider_sec_api.run_sec_api_on_demand",
            side_effect=AssertionError("UNAUTHORIZED")) as vendor:
            render_single_ticker_search(st)
        vendor.assert_not_called()
        self.assertEqual([disabled for name,disabled in st.buttons if name==label],
                         [True])



class P254PeerSourceReplayTests(unittest.TestCase):
    """Direct Engine C join must replay mapping + filing bytes, not just hash."""

    def _join(self, raw=None, **changes):
        from proofinvest.ticker_vendor_peer import build_peer_comparison
        original = raw if raw is not None else peer_responses()
        inputs = {
            "peer_ticker": "AAPL", "peer_cik": "0000320193",
            "peer_accession": "0000320193-25-000020",
            "peer_filing_date": "2025-10-15",
            "peer_period_end": "2025-09-30",
            "peer_mapping_raw": original[4], "peer_query_raw": original[5],
            "peer_xbrl_raw": original[6], "industry": "Semiconductors",
            "target_cik": "0001045810", "target_ticker": "NVDA",
            "target_prior_revenue_usd": "100",
            "target_current_revenue_usd": "200",
            "target_prior_end": "2024-09-30",
            "target_current_end": "2025-09-30", "as_of": "2026-02-01",
        }
        inputs.update(changes)
        return build_peer_comparison(**inputs)

    def test_original_peer_source_replay_preserves_descriptive_result(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("UNAUTHORIZED_HTTP")):
            result = self._join()
        self.assertEqual(result["status"], "PEER_ONE_PERIOD_ALIGNED_UNVERIFIED")
        self.assertEqual(result["peer_growth_pct"], "50.00")
        self.assertEqual(result["growth_gap_to_one_peer_pp"], "50.00")
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["full_engine_c_ready"])

    def test_final_join_refuses_unrelated_industry_mapping(self):
        raw = peer_responses()
        rows = json.loads(raw[4])
        rows[0]["industry"] = "Other Industry"
        raw[4] = json.dumps(rows).encode()
        with self.assertRaises(ValueError):
            self._join(raw)

    def test_final_join_refuses_forged_peer_id_with_valid_raw_bodies(self):
        with self.assertRaisesRegex(ValueError, "MAPPING_REPLAY_MISMATCH"):
            self._join(peer_ticker="MSFT")
        with self.assertRaisesRegex(ValueError, "MAPPING_REPLAY_MISMATCH"):
            self._join(peer_cik="0000789019")

    def test_final_join_refuses_filing_receipt_drift(self):
        with self.assertRaisesRegex(ValueError, "FILING_REPLAY_MISMATCH"):
            self._join(peer_filing_date="2025-10-16")
        with self.assertRaisesRegex(ValueError, "FILING_REPLAY_MISMATCH"):
            self._join(peer_accession="0000320193-25-000021")

    def test_final_join_rechecks_actual_filing_body(self):
        raw = peer_responses()
        record = json.loads(raw[5])
        record["filings"][0]["filedAt"] = "2025-10-16T10:00:00-04:00"
        raw[5] = json.dumps(record).encode()
        with self.assertRaisesRegex(ValueError, "FILING_REPLAY_MISMATCH"):
            self._join(raw)

    def test_final_join_rejects_future_filing_for_asof(self):
        with self.assertRaises(ValueError):
            self._join(as_of="2025-10-01")

if __name__ == "__main__":
    unittest.main()
