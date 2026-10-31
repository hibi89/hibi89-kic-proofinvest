"""P44 Market Reality: offline exact contract and no-spurious-bubble tests."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import json
import unittest
from unittest.mock import patch

from proofinvest.market_reality import (
    MAX_UPLOAD_BYTES, analyze_market_reality, parse_market_reality_json,
)


def fixture(n=45, stock_beta=Decimal("1.5"), seed=date(2025, 8, 1)):
    days = []
    day = seed
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day.isoformat())
        day += timedelta(days=1)
    market = Decimal("100")
    stock = Decimal("100")
    stock_rows = [{"date": days[0], "value": str(stock)}]
    market_rows = [{"date": days[0], "value": str(market)}]
    for i, d in enumerate(days[1:], start=1):
        movement = Decimal("0.01") if i % 2 else Decimal("-0.01")
        market *= (1 + movement)
        stock *= (1 + Decimal("0.002") + stock_beta * movement)
        stock_rows.append({"date": d, "value": str(stock.quantize(Decimal("0.00000001")))})
        market_rows.append({"date": d, "value": str(market.quantize(Decimal("0.00000001")))})
    return {
        "schema": "kuodra.market-reality.v1",
        "issuer_cik": "0000000001", "as_of": "2025-10-16",
        "symbol": "SYNTH", "benchmark": "NASDAQ_100",
        "return_basis": "PRICE_ONLY_CLOSE",
        "security": {"source": {
            "provider": "SYNTHETIC_STOCK_FEED", "url": "https://example.org/stocks",
            "published_at": "2025-10-15", "sha256": "a" * 64},
            "observations": stock_rows},
        "index": {"source": {
            "provider": "SYNTHETIC_INDEX_FEED", "url": "https://example.org/bench",
            "published_at": "2025-10-15", "sha256": "b" * 64},
            "observations": market_rows},
    }


class MarketRealityTests(unittest.TestCase):
    def test_beta_alpha_r2_from_real_decimal_ols_no_network(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NETWORK")) as http:
            out = analyze_market_reality(fixture(), expected_issuer_cik="0000000001",
                                         analysis_as_of="2025-10-16")
        http.assert_not_called()
        self.assertEqual(out["status"], "REPORTED_UNVERIFIED")
        self.assertAlmostEqual(float(out["beta"]), 1.5, places=3)
        self.assertAlmostEqual(float(out["regression_intercept_daily_pct"]), 0.2,
                               places=3)
        self.assertAlmostEqual(float(out["r_squared"]), 1.0, places=3)
        self.assertEqual(out["observation_count"], 45)
        self.assertEqual(out["return_count"], 44)
        self.assertFalse(out["market_bubble_proven"])
        self.assertFalse(out["sec_growth_caused_price_move"])
        self.assertFalse(out["guard_policy_modified"])
        self.assertFalse(out["trade_signal"])
        self.assertIsNone(out["sec_revenue_context"])

    def test_market_variance_zero_omits_beta_intercept_r2(self):
        payload = fixture()
        for row in payload["index"]["observations"]:
            row["value"] = "100.00"
        out = analyze_market_reality(payload)
        self.assertEqual(out["status"], "INSUFFICIENT_MARKET_VARIANCE")
        for key in ("beta", "regression_intercept_daily_pct", "r_squared"):
            self.assertIsNone(out[key])

    def test_zero_stock_variance_r2_undefined(self):
        obj = fixture()
        for item in obj["security"]["observations"]:
            item["value"] = "100"
        result = analyze_market_reality(obj)
        self.assertIsNone(result["r_squared"])
        self.assertEqual(result["beta"], "0.0000")

    def test_unsorted_misaligned_duplicate_and_future_date_blocked(self):
        for op in ("missing", "swap", "future", "weekend"):
            obj = fixture()
            if op == "missing":
                obj["index"]["observations"].pop()
            if op == "swap":
                arr = obj["index"]["observations"]
                arr[2], arr[3] = arr[3], arr[2]
            if op == "future":
                obj["security"]["observations"][-1]["date"] = "2026-01-05"
            if op == "weekend":
                obj["security"]["observations"][2]["date"] = "2025-08-03"
            with self.subTest(op=op), self.assertRaises(ValueError):
                analyze_market_reality(obj)

    def test_wrong_issuer_and_asof_blocked(self):
        with self.assertRaisesRegex(ValueError, "MARKET_ISSUER_MISMATCH"):
            analyze_market_reality(fixture(), expected_issuer_cik="0000000002")
        with self.assertRaisesRegex(ValueError, "MARKET_ASOF_MISMATCH"):
            analyze_market_reality(fixture(), analysis_as_of="2025-10-15")

    def test_unsupported_benchmark_and_price_value_rejected(self):
        a = fixture()
        a["benchmark"] = "NASDAQ_COMPOSITE"
        with self.assertRaises(ValueError):
            analyze_market_reality(a)
        for value in ("0", "-100", "NaN", "Infinity", "100.000000000", "1e80"):
            a = fixture()
            a["security"]["observations"][0]["value"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze_market_reality(a)

    def test_url_query_credentials_non_https_and_future_release_rejected(self):
        for url in ("http://example.org/q", "https://localhost/q",
                    "https://u:p@example.org/x", "https://example.org?key=private",
                    "https://example.org:99999/x"):
            obj = fixture()
            obj["security"]["source"]["url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                analyze_market_reality(obj)
        obj = fixture()
        obj["index"]["source"]["published_at"] = "2025-10-17"
        with self.assertRaisesRegex(ValueError, "SOURCE_PUBLISHED_AFTER_AS_OF"):
            analyze_market_reality(obj)

    def test_source_release_precedes_last_price_is_rejected(self):
        obj = fixture()
        obj["security"]["source"]["published_at"] = "2025-08-10"
        with self.assertRaisesRegex(ValueError, "SOURCE_PUBLISHED_BEFORE_LAST_PRICE_OBSERVATION"):
            analyze_market_reality(obj)

    def test_json_bounded_duplicate_nan_bad_utf8(self):
        parsed = parse_market_reality_json(json.dumps(fixture()).encode())
        self.assertEqual(analyze_market_reality(parsed)["status"], "REPORTED_UNVERIFIED")
        for raw in (b'{"a":1,"a":2}', b'{"x":NaN}', b"\xff",
                    b" " * (MAX_UPLOAD_BYTES + 1)):
            with self.subTest(raw=raw[:15]), self.assertRaises(ValueError):
                parse_market_reality_json(raw)

    def test_sec_context_is_bound_to_same_issuer_asof_guard_sha(self):
        report = {
            "schema": "proofinvest.local-sec-guard-report.v1",
            "issuer": {"cik": "0000000001", "as_of": "2025-10-16",
                       "filing_date": "2025-10-15"},
            "verification": {"status": "calculated_unverified",
                             "growth_pct": "100.00",
                             "current_period_end": "2025-09-30"},
            "source": {"companyfacts_sha256": "c" * 64},
            "guard": {"decision": "HOLD", "source_authenticated": False},
        }
        out = analyze_market_reality(fixture(), sec_review=report)
        self.assertEqual(out["sec_revenue_context"]["growth_pct_calculated_unverified"], "100.00")
        self.assertFalse(out["sec_revenue_context"]["source_authenticated"])
        for modify in (
            {"issuer": report["issuer"] | {"cik": "0000000003"}},
            {"issuer": report["issuer"] | {"as_of": "2025-10-15"}},
            {"source": {"companyfacts_sha256": "bad-sha"}},
        ):
            with self.subTest(modify=modify), self.assertRaises(ValueError):
                analyze_market_reality(fixture(), sec_review=report | modify)
        self.assertIsNone(analyze_market_reality(
            fixture(), sec_review=report | {"guard": {"decision": "REJECT",
                                              "source_authenticated": False}}
        )["sec_revenue_context"])

    def test_no_valuation_or_bubble_claim_in_report(self):
        s = json.dumps(analyze_market_reality(fixture()), ensure_ascii=False)
        self.assertIn('"market_bubble_proven": false', s)
        self.assertNotIn('"market_bubble_pct"', s)
        self.assertNotIn('"stock_target"', s)


if __name__ == "__main__":
    unittest.main()
