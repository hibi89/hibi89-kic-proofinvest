"""P101: source-SHA-bound same-10-K fiscal arithmetic; no HTTP or Guard."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.ticker_sec_financial_bridge import inspect_collected_annual_revenue
from proofinvest import ticker_sec_transport as transport
from tests.test_ticker_sec_transport import payloads, UA, Response


def valid_case():
    source = payloads()
    url = transport.SEC_API + "/api/xbrl/companyfacts/CIK0001045810.json"
    # Annual starts have 365 days. Two endpoints from one same 10-K.
    rows = [
        {"accn": "0001045810-25-000020", "form": "10-K",
         "start": "2024-10-01", "end": "2025-09-30",
         "filed": "2025-10-15", "val": 200},
        {"accn": "0001045810-25-000020", "form": "10-K",
         "start": "2023-10-01", "end": "2024-09-30",
         "filed": "2025-10-15", "val": 100},
    ]
    source[url] = Response(
        json.dumps({"cik": 1045810, "facts": {
            "us-gaap": {"RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {"USD": rows}}}
        }}).encode(), url,
    )
    def fake(request, *, timeout):
        return source[request.full_url]
    with patch.object(transport, "_open_once", side_effect=fake), \
            patch.object(transport.time, "sleep", return_value=None):
        receipt, raw = transport.collect_ticker_sec_sources(
            ticker="NVDA", as_of="2025-10-16", user_agent=UA,
            allow_network=True, acknowledge_four_requests=True,
        )
    assert receipt["status"] == "four_sec_responses_in_memory_unverified"
    return receipt, raw


class BridgeTests(unittest.TestCase):
    def test_same_filing_revenue_growth_and_provenance(self):
        receipt, raw = valid_case()
        with patch.object(transport, "_open_once", side_effect=AssertionError("NO_NETWORK")) as net:
            result = inspect_collected_annual_revenue(receipt, raw)
        net.assert_not_called()
        self.assertEqual(result["status"], "REVENUE_CALCULATED_UNVERIFIED", result)
        self.assertEqual(result["growth_pct"], "100.00")
        self.assertEqual(result["current_usd"], "200")
        self.assertEqual(result["prior_usd"], "100")
        self.assertEqual(result["current_end"], "2025-09-30")
        self.assertEqual(result["prior_end"], "2024-09-30")
        self.assertEqual(result["companyfacts_sha256"], sha256(raw["companyfacts"]).hexdigest())
        for k in ("source_authenticated","source_rights_verified",
                  "original_10k_text_verified", "engine_a_ready",
                  "engine_b_full_ready", "engine_c_ready", "guard_executed",
                  "ai_interpretation_ready", "trade_executed"):
            self.assertIs(result[k], False, k)

    def test_missing_sources_wrong_receipt_and_default_no_network(self):
        receipt, raw = valid_case()
        for mutated_receipt, mutated_raw in (
            ({}, raw), (receipt, None),
            ({**receipt, "source_authenticated": True}, raw),
            ({**receipt, "http_requests_attempted": 5}, raw),
            (receipt, {k:v for k,v in raw.items() if k != "original_10k"}),
        ):
            with self.subTest(mutated_receipt=bool(mutated_receipt), has_raw=bool(mutated_raw)):
                result = inspect_collected_annual_revenue(mutated_receipt, mutated_raw)
                self.assertEqual(result["status"], "UNAVAILABLE")
                self.assertIsNone(result["growth_pct"])

    def test_changed_companyfacts_or_original_sha_refused(self):
        receipt, raw = valid_case()
        for name in ("ticker_map","submissions","companyfacts","original_10k"):
            modified = dict(raw, **{name: raw[name] + b" "})
            with self.subTest(name=name):
                r = inspect_collected_annual_revenue(receipt, modified)
                self.assertEqual(r["status"], "UNAVAILABLE")
                self.assertIsNone(r["growth_pct"])

    def test_url_cik_or_filing_mutation_blocked(self):
        receipt, raw = valid_case()
        cases = [
            {"cik": "0000000002"},
            {"ticker": "AAPL"},
            {"selected_10k_accession": "0001045810-24-000010"},
            {"selected_10k_filing_date": "2025-10-16"},
            {"source_urls": {"companyfacts": "https://evil.example/x"}},
            {"requested_as_of": "2024-01-01"},
        ]
        for updates in cases:
            result = inspect_collected_annual_revenue(receipt | updates, raw)
            self.assertEqual(result["status"], "UNAVAILABLE", updates)
            self.assertIsNone(result["current_usd"])

    def test_cross_filing_revenue_not_promoted(self):
        receipt, raw = valid_case()
        facts=json.loads(raw["companyfacts"])
        rows=facts["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
        rows[1]["accn"]="0001045810-24-000010"
        modified=json.dumps(facts).encode()
        receipt=deepcopy(receipt)
        receipt["source_sha256"]["companyfacts"]=sha256(modified).hexdigest()
        receipt["source_bytes"]["companyfacts"]=len(modified)
        result=inspect_collected_annual_revenue(receipt,raw | {"companyfacts":modified})
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIsNone(result["growth_pct"])

    def test_foreign_companyfacts_cik_blocked(self):
        receipt, raw = valid_case()
        obj=json.loads(raw["companyfacts"])
        obj["cik"]=17
        changed=json.dumps(obj).encode()
        receipt=deepcopy(receipt)
        receipt["source_sha256"]["companyfacts"]=sha256(changed).hexdigest()
        receipt["source_bytes"]["companyfacts"]=len(changed)
        result=inspect_collected_annual_revenue(receipt,raw | {"companyfacts":changed})
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["reason_code"], "COMPANYFACTS_ISSUER_MISMATCH")

    def test_duplicate_annual_values_and_mixed_concepts_rejected(self):
        receipt, raw = valid_case()
        obj=json.loads(raw["companyfacts"])
        usgaap=obj["facts"]["us-gaap"]
        rows=usgaap["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
        rows.append({**rows[0], "val": 201})
        bad=json.dumps(obj).encode()
        pinned=deepcopy(receipt)
        pinned["source_sha256"]["companyfacts"]=sha256(bad).hexdigest()
        pinned["source_bytes"]["companyfacts"]=len(bad)
        out=inspect_collected_annual_revenue(pinned,raw | {"companyfacts":bad})
        self.assertEqual(out["status"], "UNAVAILABLE")
        self.assertIsNone(out["growth_pct"])

    def test_future_filing_or_future_period_never_calculated(self):
        receipt, raw = valid_case()
        for cutoff in ("2024-12-01","2025-10-14"):
            out=inspect_collected_annual_revenue(receipt | {"requested_as_of": cutoff}, raw)
            self.assertEqual(out["status"], "UNAVAILABLE")
        obj=json.loads(raw["companyfacts"])
        rows=obj["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
        rows[0]["filed"]="2025-11-01"
        changed=json.dumps(obj).encode()
        pinned=deepcopy(receipt)
        pinned["source_sha256"]["companyfacts"]=sha256(changed).hexdigest()
        pinned["source_bytes"]["companyfacts"]=len(changed)
        out=inspect_collected_annual_revenue(pinned,raw | {"companyfacts":changed})
        self.assertEqual(out["status"], "UNAVAILABLE")

    def test_no_matching_annual_period_no_fabricated_growth(self):
        receipt, raw = valid_case()
        obj=json.loads(raw["companyfacts"])
        usgaap=obj["facts"]["us-gaap"]
        usgaap["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"].pop()
        modified=json.dumps(obj).encode()
        receipt=deepcopy(receipt)
        receipt["source_sha256"]["companyfacts"]=sha256(modified).hexdigest()
        receipt["source_bytes"]["companyfacts"]=len(modified)
        out=inspect_collected_annual_revenue(receipt,raw | {"companyfacts":modified})
        self.assertEqual(out["status"], "UNAVAILABLE")
        self.assertIsNone(out["growth_pct"])


if __name__ == "__main__":
    unittest.main()
