"""P145 one-ticker real-shape licensed vendor 4-request contract offline."""
from __future__ import annotations

from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch

from proofinvest.ticker_provider_sec_api import run_sec_api_on_demand, encode_vendor_evidence_json
from proofinvest import ticker_research_ui as ui
from tests.test_ticker_market_industry_bridge import scenario
from tests.test_ticker_research_ui import FakeSt


_GATES = {
    "KUODRA_ENABLE_SEC_API_VENDOR": "1",
    "KUODRA_SEC_API_VENDOR_RETRIEVAL_APPROVED": "1",
    "KUODRA_SEC_API_VENDOR_RIGHTS_APPROVED": "1",
}
_KEY = "SYNTHETIC-CONTRACT-KEY-NO-REQUESTS"


def vendor_responses():
    _, original, _, _ = scenario()
    raw_cf = json.loads(original["companyfacts"])
    revenue = next(iter(raw_cf["facts"]["us-gaap"].values()))["units"]["USD"]
    m = [{"ticker": "NVDA", "cik": "1045810", "name": "SYNTHETIC ISSUER"}]
    q = {"filings": [{
        "formType": "10-K", "accessionNo": "0001045810-25-000020",
        "cik": "1045810", "ticker": "NVDA",
        "filedAt": "2025-10-15T10:00:00-04:00",
        "periodOfReport": "2025-09-30",
        "linkToFilingDetails":
            "https://www.sec.gov/Archives/edgar/data/1045810/"
            "000104581025000020/annual2025.htm",
    }]}
    x = {"CoverPage": {
        "DocumentType": "10-K", "DocumentPeriodEndDate": "2025-09-30",
        "EntityCentralIndexKey": "0001045810"},
        "StatementsOfIncome": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": [
                {"value": str(v["val"]), "unitRef": "usd",
                 "period": {"startDate": v["start"], "endDate": v["end"]}}
                for v in revenue
            ],
        }}
    return [json.dumps(m).encode(), json.dumps(q).encode(),
            json.dumps(x).encode(), original["original_10k"]]


def fake_call(payloads, recorded):
    def read(method, url, body, key, limit):
        recorded.append((method, url, body, key, limit))
        return payloads[len(recorded) - 1]
    return read


class SecApiOneTickerTests(unittest.TestCase):
    def invoke(self, **changes):
        bodies = vendor_responses()
        observed = []
        args = {
            "ticker": "NVDA", "as_of": "2026-02-01",
            "api_key": _KEY, "explicit_click": True,
            "operator_retrieval_approved": True,
            "operator_rights_approved": True,
            "transport": fake_call(bodies, observed),
        }
        args.update(changes)
        with patch.dict(os.environ, _GATES, clear=True):
            result = run_sec_api_on_demand(**args)
        return result, observed

    def test_four_real_vendor_shapes_reach_seven_stage_a_b_c_guard_report(self):
        result, seen = self.invoke()
        self.assertEqual(result["status"], "SOURCE_REPLAYED_UNVERIFIED", result)
        self.assertEqual(result["provider_http_requests_attempted"], 4)
        self.assertEqual([row[0] for row in seen], ["GET", "POST", "GET", "GET"])
        self.assertEqual([row[1].split("/")[2] for row in seen],
                         ["api.sec-api.io", "api.sec-api.io",
                          "api.sec-api.io", "edgar-mirror.sec-api.io"])
        self.assertIn("cik:1045810", seen[1][2].decode())
        self.assertEqual(result["report"]["guard_policy_preview"], "HOLD")
        self.assertEqual(result["dashboard"]["engine_b"]["status"], "UNAVAILABLE")
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["source_rights_verified"])
        self.assertFalse(result["redistribution_allowed"])
        self.assertFalse(result["full_a_b_c_ready"])
        self.assertFalse(result["trade_executed"])
        self.assertEqual(result["source_kind"],
                         "THIRD_PARTY_XBRL_TO_SEC_SHAPED_UNAUTHENTICATED")
        self.assertNotIn(_KEY, json.dumps(result))
        self.assertNotIn("<?xml", json.dumps(result))

    def test_export_bundle_explicitly_marks_vendor_derived_sec_shaped_data(self):
        result, seen = self.invoke()
        self.assertEqual(result["status"], "SOURCE_REPLAYED_UNVERIFIED")
        payload = json.loads(encode_vendor_evidence_json(result))
        self.assertEqual(payload["vendor"], "SEC_API_IO")
        self.assertTrue(payload["derived_sec_shaped_data_not_original_sec_json"])
        self.assertFalse(payload["source_rights_verified"])
        self.assertFalse(payload["redistribution_allowed"])
        self.assertEqual(payload["original_local_report_sha256"],
                         payload["local_report"]["report_sha256"])
        self.assertNotIn(_KEY, json.dumps(payload))
        self.assertNotIn("StatementsOfIncome", json.dumps(payload))
        self.assertNotIn("<?xml", json.dumps(payload))
        tampered = dict(result, source_authenticated=True)
        with self.assertRaises(ValueError):
            encode_vendor_evidence_json(tampered)

    def test_environment_or_click_missing_prevents_any_vendor_transport(self):
        seen = []
        for kw in ({"explicit_click": False},
                   {"operator_rights_approved": False},
                   {"ticker": "../NVDA"}, {"as_of": "2099-02-01"}):
            response, calls = self.invoke(**kw, transport=lambda *_: seen.append(1))
            self.assertEqual(response["status"], "BLOCKED")
            self.assertEqual(calls, [])
        self.assertFalse(seen)
        with patch.dict(os.environ, {}, clear=True):
            out = run_sec_api_on_demand(
                ticker="NVDA", as_of="2026-02-01", api_key=_KEY,
                explicit_click=True, operator_rights_approved=True,
                operator_retrieval_approved=True,
                transport=lambda *_: self.fail("NETWORK"))
        self.assertEqual(out["status"], "BLOCKED")

    def test_mismatched_vendor_cik_name_or_ticker_refused_before_full_fetch(self):
        for key, replacement in (("ticker", "AAPL"), ("cik", "320193")):
            raws = vendor_responses()
            m = json.loads(raws[0])
            m[0][key] = replacement
            raws[0] = json.dumps(m).encode()
            calls = []
            out, seen = self.invoke(transport=fake_call(raws, calls))
            self.assertEqual(out["status"], "BLOCKED", out)
            self.assertEqual(out["provider_http_requests_attempted"],
                             1 if key == "ticker" else 2)

    def test_filing_future_or_unsafe_original_path_never_fetches_xbrl(self):
        for changed in ("future", "evil", "wrong_cik"):
            raws = vendor_responses()
            filings = json.loads(raws[1])
            row = filings["filings"][0]
            if changed == "future":
                row["filedAt"] = "2030-01-01T00:00:00-05:00"
            elif changed == "evil":
                row["linkToFilingDetails"] = "https://evil.example/annual.htm"
            else:
                row["cik"] = "320193"
            raws[1] = json.dumps(filings).encode()
            calls = []
            out, _ = self.invoke(transport=fake_call(raws, calls))
            self.assertEqual(out["status"], "BLOCKED")
            self.assertEqual(out["provider_http_requests_attempted"], 2)

    def test_vendor_xbrl_conflicting_identity_and_missing_revenue_stop_before_original(self):
        for change in ("cik", "period", "revenue"):
            raws = vendor_responses()
            statement = json.loads(raws[2])
            if change == "cik":
                statement["CoverPage"]["EntityCentralIndexKey"] = "0000320193"
            elif change == "period":
                statement["CoverPage"]["DocumentPeriodEndDate"] = "2024-09-30"
            else:
                statement["StatementsOfIncome"].clear()
            raws[2] = json.dumps(statement).encode()
            calls = []
            out, _ = self.invoke(transport=fake_call(raws, calls))
            self.assertEqual(out["status"], "BLOCKED")
            self.assertEqual(out["provider_http_requests_attempted"], 3)

    def test_vendor_429_and_error_no_retry_or_side_effect(self):
        def failed(*_):
            raise ValueError("RATE_LIMIT_429")
        out, calls = self.invoke(transport=failed)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["provider_http_requests_attempted"], 1)
        self.assertEqual(calls, [])
        self.assertIsNone(out["report"])

    def test_original_rejected_on_wrong_mime_bytes_and_no_more_network(self):
        raws = vendor_responses()
        raws[-1] = b"not a filing"
        calls = []
        out, _ = self.invoke(transport=fake_call(raws, calls))
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["provider_http_requests_attempted"], 4)

    def test_vendor_button_disabled_without_env_even_click_intent(self):
        st = FakeSt(clicked="승인된 공급자로 10-K 조회 → A/B/C·Guard·근거 보고서 (최대 4회)")
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}, clear=True):
            ui.render_single_ticker_search(st)
        matched = [off for title, off in st.buttons if title.startswith("승인된 공급자로 10-K")]
        self.assertEqual(matched, [True])

    def test_vendor_button_receipt_and_report_download_with_fake_provider(self):
        result, _ = self.invoke()
        st = FakeSt(
            clicked="승인된 공급자로 10-K 조회 → A/B/C·Guard·근거 보고서 (최대 4회)",
            values={"kuodra_p100_ticker": "NVDA", "kuodra_p100_as_of": "2026-02-01"},
            checks={"kuodra_p145_vendor_ack": True},
        )
        env = {**_GATES, "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
               "KUODRA_SEC_API_VENDOR_KEY": _KEY}
        with patch.dict(os.environ, env, clear=True), patch(
            "proofinvest.ticker_provider_sec_api.run_sec_api_on_demand",
            return_value=result,
        ) as provider:
            ui.render_single_ticker_search(st)
        provider.assert_called_once()
        self.assertTrue(any(kind == "download" and
                            val["file_name"] == "kuodra-vendor-local-review-UNVERIFIED.json"
                            for kind, val in st.messages))
        self.assertNotIn(_KEY, str(st.messages))
        for kind, value in st.messages:
            if kind == "download" and value["file_name"].startswith("kuodra-vendor-"):
                document = json.loads(value["data"])
                self.assertTrue(document["derived_sec_shaped_data_not_original_sec_json"])
                self.assertEqual(document["vendor"], "SEC_API_IO")


if __name__ == "__main__":
    unittest.main()
