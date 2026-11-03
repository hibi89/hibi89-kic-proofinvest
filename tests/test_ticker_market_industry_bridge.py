"""P104 single ticker optional A/C source join: mocked, fail-closed."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.ticker_market_industry_bridge import evaluate_ticker_a_c
from tests.test_ticker_sec_financial_bridge import valid_case
from tests.test_ixbrl_revenue_review import xhtml
from tests.test_market_reality import fixture as market_fixture
from tests.test_industry_vision import fixture as industry_fixture


def scenario():
    receipt, raw = valid_case()
    receipt = deepcopy(receipt)
    receipt["requested_as_of"] = "2026-02-01"
    original = xhtml().replace(b"0000000001</xbrli:identifier>",
                               b"0001045810</xbrli:identifier>")
    raw = dict(raw, original_10k=original)
    receipt["source_sha256"]["original_10k"] = sha256(original).hexdigest()
    receipt["source_bytes"]["original_10k"] = len(original)

    m = market_fixture(n=45, seed=date(2025, 11, 3))
    m["issuer_cik"] = "0001045810"
    m["symbol"] = "NVDA"
    m["as_of"] = "2026-02-01"
    for k in ("security", "index"):
        m[k]["source"]["published_at"] = "2026-01-30"

    c = industry_fixture()
    c["issuer_cik"] = "0001045810"
    c["as_of"] = "2026-02-01"
    c["prior_period_end"] = "2024-09-30"
    c["current_period_end"] = "2025-09-30"
    c["target"]["cik"] = "0001045810"
    c["target"]["prior_revenue_usd"] = "100"
    c["target"]["current_revenue_usd"] = "200"
    for item in c["sources"]:
        item["published_at"] = "2025-10-15"
        if item["id"] in ("target-old", "target-now"):
            item["sha256"] = receipt["source_sha256"]["companyfacts"]
    return receipt, raw, m, c


class TickerMarketIndustryBridgeTests(unittest.TestCase):
    def test_missing_provider_is_explicit_unavailable_not_fabricated(self):
        receipt, raw, _, _ = scenario()
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")) as net:
            result = evaluate_ticker_a_c(receipt, raw)
        net.assert_not_called()
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["engine_a"]["status"], "UNAVAILABLE")
        self.assertEqual(result["engine_c"]["status"], "UNAVAILABLE")
        self.assertFalse(result["all_three_engines_ready"])

    def test_market_and_industry_same_ticker_period_receipt(self):
        receipt, raw, m, c = scenario()
        result = evaluate_ticker_a_c(
            receipt, raw, market_json=json.dumps(m).encode(),
            industry_json=json.dumps(c).encode())
        self.assertEqual(result["status"], "PARTIAL_SOURCE_ANALYSIS_UNVERIFIED", result)
        self.assertEqual(result["engine_a"]["status"], "REPORTED_UNVERIFIED", result)
        self.assertEqual(result["engine_c"]["status"], "OBSERVED_COMPARISON_UNVERIFIED", result)
        self.assertEqual(result["engine_a"]["observation_count"], 45)
        self.assertEqual(result["engine_c"]["peer_count"], 1)
        self.assertEqual(result["engine_c"]["growth_gap_to_industry_pp"], "80.00")
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["all_three_engines_ready"])
        self.assertFalse(result["guard_executed"])
        self.assertFalse(result["audit_written"])
        self.assertFalse(result["trade_executed"])

    def test_market_other_ticker_or_issuer_denied(self):
        receipt, raw, m, _ = scenario()
        for key, replacement in (("symbol", "AAPL"), ("issuer_cik", "0000320193"),
                                 ("as_of", "2026-01-31")):
            altered = deepcopy(m)
            altered[key] = replacement
            r = evaluate_ticker_a_c(receipt, raw,
                                    market_json=json.dumps(altered).encode())
            self.assertEqual(r["engine_a"]["status"], "UNAVAILABLE", key)
            self.assertIsNone(r["engine_a"]["input_sha256"])

    def test_price_window_before_10k_filing_not_merged(self):
        receipt, raw, m, _ = scenario()
        old = market_fixture(n=45, seed=date(2025, 8, 1))
        old["issuer_cik"], old["symbol"], old["as_of"] = (
            "0001045810", "NVDA", "2026-02-01")
        for k in ("security", "index"):
            old[k]["source"]["published_at"] = "2026-01-30"
        result = evaluate_ticker_a_c(receipt, raw,
                                     market_json=json.dumps(old).encode())
        self.assertEqual(result["engine_a"]["status"], "UNAVAILABLE")
        self.assertEqual(result["engine_a"]["reason_code"],
                         "MARKET_SOURCE_OR_PERIOD_NOT_COMPATIBLE")

    def test_industry_wrong_period_or_target_amount_denied(self):
        receipt, raw, _, c = scenario()
        for modify in ("prior_period", "target_revenue", "target_cik", "source_sha"):
            data = deepcopy(c)
            if modify == "prior_period":
                data["prior_period_end"] = "2024-12-31"
            elif modify == "target_revenue":
                data["target"]["current_revenue_usd"] = "201"
            elif modify == "target_cik":
                data["target"]["cik"] = "0000320193"
            else:
                data["sources"][0]["sha256"] = "a" * 64
            result = evaluate_ticker_a_c(receipt, raw,
                                         industry_json=json.dumps(data).encode())
            self.assertEqual(result["engine_c"]["status"], "UNAVAILABLE", modify)

    def test_engine_c_rejects_cross_company_source_reuse_without_blocking_a(self):
        receipt, raw, m, c = scenario()
        for attack in ("same_source_id", "same_source_sha"):
            changed = deepcopy(c)
            if attack == "same_source_id":
                changed["peers"][0]["prior_source_id"] = "target-old"
            else:
                original = {x["id"]: x for x in changed["sources"]}
                original["peer-old"]["sha256"] = original["target-old"]["sha256"]
            result = evaluate_ticker_a_c(
                receipt, raw, market_json=json.dumps(m).encode(),
                industry_json=json.dumps(changed).encode())
            with self.subTest(attack=attack):
                self.assertEqual(result["engine_c"]["status"], "UNAVAILABLE")
                self.assertEqual(result["engine_c"]["reason_code"],
                                 "INDUSTRY_SOURCE_OR_FISCAL_COHORT_NOT_COMPATIBLE")
                self.assertIsNone(result["engine_c"]["input_sha256"])
                self.assertEqual(result["engine_a"]["status"],
                                 "REPORTED_UNVERIFIED")
                self.assertFalse(result["source_authenticated"])

    def test_untrusted_sec_or_conflicting_dei_blocks_both(self):
        receipt, raw, m, c = scenario()
        altered = deepcopy(receipt)
        altered["source_sha256"]["companyfacts"] = "0" * 64
        out = evaluate_ticker_a_c(altered, raw,
                                  market_json=json.dumps(m).encode(),
                                  industry_json=json.dumps(c).encode())
        self.assertEqual(out["status"], "UNAVAILABLE")
        self.assertIsNone(out["issuer_cik"])
        self.assertEqual(out["engine_a"]["status"], "UNAVAILABLE")
        self.assertEqual(out["engine_c"]["status"], "UNAVAILABLE")
        # Embedded self-declared wrong issuer cannot be promoted to engine A/C.
        original = raw["original_10k"].replace(
            b"</body>",
            b'<ix:nonNumeric name="dei:EntityCentralIndexKey">0000320193</ix:nonNumeric>'
            b'<ix:nonNumeric name="dei:DocumentType">10-K</ix:nonNumeric></body>')
        altered = deepcopy(receipt)
        raw2 = dict(raw, original_10k=original)
        altered["source_sha256"]["original_10k"] = sha256(original).hexdigest()
        altered["source_bytes"]["original_10k"] = len(original)
        rejected = evaluate_ticker_a_c(altered, raw2,
                                       market_json=json.dumps(m).encode())
        self.assertEqual(rejected["status"], "UNAVAILABLE")
        self.assertEqual(rejected["reason_code"],
                         "SEC_ORIGINAL_CONTEXT_OR_GUARD_NOT_ELIGIBLE")

    def test_one_engine_missing_does_not_suppress_other_valid_engine(self):
        receipt, raw, m, c = scenario()
        corrupted_c = deepcopy(c)
        corrupted_c["sources"][0]["sha256"] = "a" * 64
        res = evaluate_ticker_a_c(receipt, raw,
                                   market_json=json.dumps(m).encode(),
                                   industry_json=json.dumps(corrupted_c).encode())
        self.assertEqual(res["engine_a"]["status"], "REPORTED_UNVERIFIED")
        self.assertEqual(res["engine_c"]["status"], "UNAVAILABLE")
        self.assertFalse(res["all_three_engines_ready"])

    def test_json_nonfinite_duplicate_and_oversize_refused(self):
        receipt, raw, m, c = scenario()
        for raw_input in (b'{"x":NaN}', b'{"x":1,"x":2}',
                          b"x" * 140000):
            res = evaluate_ticker_a_c(receipt, raw, market_json=raw_input)
            self.assertEqual(res["engine_a"]["status"], "UNAVAILABLE")
            self.assertIsNone(res["engine_a"]["input_sha256"])

    def test_no_side_effects_and_no_provider_http(self):
        receipt, raw, m, c = scenario()
        with patch("urllib.request.urlopen", side_effect=AssertionError("NETWORK")) as net:
            res = evaluate_ticker_a_c(receipt, raw,
                                      market_json=json.dumps(m).encode(),
                                      industry_json=json.dumps(c).encode())
        net.assert_not_called()
        self.assertFalse(res["audit_written"])
        self.assertFalse(res["trade_executed"])


if __name__ == "__main__":
    unittest.main()
