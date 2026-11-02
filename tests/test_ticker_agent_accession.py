"""P103 agent-submitted SEC accession: same issuer, different submitter CIK.

Transport is mocked; no actual SEC requests or authentication upgrades.
"""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from proofinvest import ticker_sec_transport as transport
from proofinvest.ticker_sec_financial_bridge import inspect_collected_annual_revenue
from proofinvest.ticker_sec_original_guard_preview import inspect_original_guard_preview
from tests.test_ticker_sec_transport import Response, UA, payloads
from tests.test_ticker_sec_financial_bridge import valid_case
from tests.test_ixbrl_revenue_review import xhtml

ISSUER = "0001045810"
SUBMITTER = "0000999999"
AGENT_ACC = "0000999999-25-000020"
COMPANYFACTS_URL = transport.SEC_API + "/api/xbrl/companyfacts/CIK" + ISSUER + ".json"
SUBMISSIONS_URL = transport.SEC_API + "/submissions/CIK" + ISSUER + ".json"
ORIGINAL_URL = (transport.SEC_ARCHIVE + "/1045810/"
                + AGENT_ACC.replace("-", "") + "/annual2025.htm")


def agent_payloads():
    # Reuses the exact same P101 synthetic annual USD cohort (200/100).
    _, original = valid_case()
    sources = payloads()
    submissions = json.loads(original["submissions"])
    submissions["filings"]["recent"]["accessionNumber"][1] = AGENT_ACC
    sources[SUBMISSIONS_URL] = Response(
        json.dumps(submissions).encode(), SUBMISSIONS_URL,
    )
    companyfacts = json.loads(original["companyfacts"])
    rows = companyfacts["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
    for row in rows:
        row["accn"] = AGENT_ACC
    sources[COMPANYFACTS_URL] = Response(
        json.dumps(companyfacts).encode(), COMPANYFACTS_URL,
    )
    previous_url = next(url for url in sources if "/annual2025.htm" in url)
    del sources[previous_url]
    source_xhtml = xhtml().replace(
        b"0000000001</xbrli:identifier>",
        b"0001045810</xbrli:identifier>",
    )
    sources[ORIGINAL_URL] = Response(source_xhtml, ORIGINAL_URL, "text/html")
    return sources


def run_mocked(sources):
    attempted = []
    def get(request, *, timeout):
        attempted.append(request.full_url)
        return sources[request.full_url]
    with patch.object(transport, "P105_SEC_403_HOLD", False), \
            patch.object(transport, "_open_once", side_effect=get), \
            patch.object(transport.time, "sleep", return_value=None):
        result, raw = transport.collect_ticker_sec_sources(
            ticker="NVDA", as_of="2025-10-16",
            user_agent=UA, allow_network=True,
            acknowledge_four_requests=True,
        )
    return result, raw, attempted


class AgentAccessionTests(unittest.TestCase):
    def test_agent_submission_four_sources_bridge_and_original_preview(self):
        result, raw, attempted = run_mocked(agent_payloads())
        self.assertEqual(result["status"], "four_sec_responses_in_memory_unverified")
        self.assertEqual(result["cik"], ISSUER)
        self.assertEqual(result["selected_10k_accession"], AGENT_ACC)
        self.assertEqual(result["source_urls"]["original_10k"], ORIGINAL_URL)
        self.assertEqual(attempted, [
            transport.MAP_URL, SUBMISSIONS_URL, COMPANYFACTS_URL, ORIGINAL_URL,
        ])
        self.assertEqual(result["http_requests_attempted"], 4)
        finance = inspect_collected_annual_revenue(result, raw)
        self.assertEqual(finance["status"], "REVENUE_CALCULATED_UNVERIFIED", finance)
        self.assertEqual(finance["accession"], AGENT_ACC)
        self.assertEqual(finance["issuer_cik"], ISSUER)
        self.assertEqual(finance["growth_pct"], "100.00")
        guard = inspect_original_guard_preview(
            result, raw, expected_revenue=finance,
        )
        self.assertEqual(guard["status"], "ORIGINAL_CONTEXT_MATCH_UNVERIFIED", guard)
        self.assertEqual(guard["guard_preview"]["decision"], "HOLD")
        self.assertFalse(guard["guard_executed"])
        self.assertFalse(guard["source_authenticated"])
        self.assertFalse(guard["audit_written"])
        self.assertFalse(guard["trade_executed"])

    def test_agent_acc_not_present_in_issuer_companyfacts_never_invents_revenue(self):
        src = agent_payloads()
        original_facts = json.loads(src[COMPANYFACTS_URL].raw)
        rows = original_facts["facts"]["us-gaap"][
            "RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
        for row in rows:
            row["accn"] = "0001045810-25-000020"
        src[COMPANYFACTS_URL] = Response(
            json.dumps(original_facts).encode(), COMPANYFACTS_URL,
        )
        result, raw, attempted = run_mocked(src)
        self.assertEqual(result["status"], "four_sec_responses_in_memory_unverified")
        self.assertEqual(len(attempted), 4)
        finance = inspect_collected_annual_revenue(result, raw)
        self.assertEqual(finance["status"], "UNAVAILABLE")
        self.assertIsNone(finance["growth_pct"])
        guard = inspect_original_guard_preview(result, raw)
        self.assertEqual(guard["status"], "UNAVAILABLE")
        self.assertIsNone(guard["guard_preview"])

    def test_forged_unrelated_issuer_submissions_blocked_at_second_get(self):
        src = agent_payloads()
        doc = json.loads(src[SUBMISSIONS_URL].raw)
        doc["cik"] = 320193
        src[SUBMISSIONS_URL] = Response(json.dumps(doc).encode(), SUBMISSIONS_URL)
        result, raw, attempted = run_mocked(src)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["stage"], "submissions")
        self.assertEqual(result["http_requests_attempted"], 2)
        self.assertEqual(attempted, [transport.MAP_URL, SUBMISSIONS_URL])
        self.assertIsNone(raw)

    def test_agent_accession_unsafe_filename_fails_before_original_get(self):
        src = agent_payloads()
        doc = json.loads(src[SUBMISSIONS_URL].raw)
        doc["filings"]["recent"]["primaryDocument"][1] = "../secret.html"
        src[SUBMISSIONS_URL] = Response(json.dumps(doc).encode(), SUBMISSIONS_URL)
        result, raw, attempted = run_mocked(src)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["stage"], "submissions")
        self.assertEqual(attempted, [transport.MAP_URL, SUBMISSIONS_URL])
        self.assertIsNone(raw)

    def test_duplicate_agent_filing_metadata_rejected(self):
        src = agent_payloads()
        doc = json.loads(src[SUBMISSIONS_URL].raw)
        for key in ("form", "accessionNumber", "filingDate",
                    "reportDate", "primaryDocument"):
            doc["filings"]["recent"][key].append(
                doc["filings"]["recent"][key][1]
            )
        src[SUBMISSIONS_URL] = Response(json.dumps(doc).encode(), SUBMISSIONS_URL)
        result, raw, attempted = run_mocked(src)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["stage"], "submissions")
        self.assertEqual(len(attempted), 2)
        self.assertIsNone(raw)

    def test_network_without_per_request_consent_still_disabled(self):
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("NO NETWORK")) as called:
            receipt, raw = transport.collect_ticker_sec_sources(
                ticker="NVDA", as_of="2025-10-16", user_agent=UA,
            )
        called.assert_not_called()
        self.assertEqual(receipt["http_requests_attempted"], 0)
        self.assertEqual(receipt["status"], "unavailable")
        self.assertIsNone(raw)


if __name__ == "__main__":
    unittest.main()
