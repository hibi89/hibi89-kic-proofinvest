"""Premium real-index adapter tests. Zero live HTTP or account changes."""
from __future__ import annotations

from datetime import date, timedelta
import json
import os
import unittest
from unittest.mock import patch
from proofinvest.market_provider_alpha_vantage_index import (
    _MAX_RESPONSE, fetch_index_daily, parse_index_daily_bytes)

KEY = "SYNTHETICKEY12345"
GATES = {"KUODRA_ENABLE_ALPHA_VANTAGE_INDEX": "1",
         "KUODRA_ALPHA_VANTAGE_INDEX_PREMIUM_APPROVED": "1",
         "KUODRA_ALPHA_VANTAGE_RIGHTS_APPROVED": "1"}


def sample_index(symbol="NDX", n=65, offset=0):
    start = date(2026, 7, 1) + timedelta(days=offset)
    series = {}
    for i in range(250):
        day = start + timedelta(days=i)
        if day.weekday() < 5:
            series[day.isoformat()] = {"4. close": str(10000 + i * 10)}
        if len(series) == n:
            break
    return json.dumps({"Meta Data": {"2. Symbol": symbol},
                       "Time Series (Daily)": series}).encode()


class IndexProviderTests(unittest.TestCase):
    def test_strict_real_index_symbol_contract(self):
        r = parse_index_daily_bytes(sample_index(), benchmark="NASDAQ_100", as_of="2026-10-01")
        self.assertEqual(r["index_symbol"], "NDX")
        self.assertEqual(r["point_count"], 65)
        self.assertFalse(r["source_rights_verified"])
        self.assertFalse(r["premium_entitlement_verified"])

    def test_premium_gate_refuses_network(self):
        seen = []
        with patch.dict(os.environ, GATES):
            for kw in ({}, {"explicit_click": True},
                       {"explicit_click": True, "rights_approved": True}):
                out = fetch_index_daily(benchmark="NASDAQ_100", as_of="2026-10-01", api_key=KEY,
                                        transport=lambda _: seen.append(1), **kw)
                self.assertEqual(out["requests_attempted"], 0)
        self.assertEqual(seen, [])

    def test_no_config_no_http(self):
        with patch.dict(os.environ, {}, clear=True):
            out = fetch_index_daily(benchmark="NASDAQ_100", as_of="2026-10-01", api_key=KEY,
                                    explicit_click=True, rights_approved=True, premium_approved=True,
                                    transport=lambda _: self.fail("UNAUTHORIZED"))
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["requests_attempted"], 0)

    def test_premium_ndx_get_only_once(self):
        called = []
        with patch.dict(os.environ, GATES):
            out = fetch_index_daily(benchmark="NASDAQ_100", as_of="2026-10-01", api_key=KEY,
                                    explicit_click=True, rights_approved=True, premium_approved=True,
                                    transport=lambda url: (called.append(url), sample_index())[1])
        self.assertEqual(out["status"], "OFFICIAL_INDEX_SYMBOL_RESPONSE_UNVERIFIED")
        self.assertEqual(len(called), 1)
        self.assertIn("function=INDEX_DATA", called[0])
        self.assertIn("symbol=NDX", called[0])
        self.assertIn("interval=daily", called[0])
        self.assertNotIn(KEY, json.dumps(out))

    def test_failure_once_no_key_leak(self):
        calls=[]
        def broken(url):
            calls.append(url)
            raise OSError("private key "+KEY)
        with patch.dict(os.environ, GATES):
            out = fetch_index_daily(benchmark="NASDAQ_100", as_of="2026-10-01", api_key=KEY,
                                    explicit_click=True, rights_approved=True, premium_approved=True,
                                    transport=broken)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["requests_attempted"], 1)
        self.assertEqual(len(calls), 1)
        self.assertNotIn(KEY, repr(out))

    def test_other_index_mislabeled_refused(self):
        with self.assertRaises(ValueError):
            parse_index_daily_bytes(sample_index("SPX"), benchmark="NASDAQ_100", as_of="2026-10-01")

    def test_duplicate_json_keys_refused(self):
        dup = b'{"Meta Data":{"2. Symbol":"NDX"},"Meta Data":{"2. Symbol":"NDX"},"Time Series (Daily)":{}}'
        with self.assertRaises(ValueError):
            parse_index_daily_bytes(dup, benchmark="NASDAQ_100", as_of="2026-10-01")

    def test_quota_notice_and_no_real_index_history_refused(self):
        for raw in (b'{"Information":"premium required"}', b'{"Note":"daily limit"}',
                    b'{}', b'not-json', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_index_daily_bytes(raw, benchmark="NASDAQ_100", as_of="2026-10-01")

    def test_synthetic_under_31_points_refused(self):
        with self.assertRaises(ValueError):
            parse_index_daily_bytes(sample_index(n=30), benchmark="NASDAQ_100", as_of="2026-10-01")

    def test_malformed_index_close_refused(self):
        bad = sample_index().replace(b'"4. close": "10000"', b'"4. close": "NaN"')
        with self.assertRaises(ValueError):
            parse_index_daily_bytes(bad, benchmark="NASDAQ_100", as_of="2026-10-01")

    def test_oversized_response_refused(self):
        with self.assertRaises(ValueError):
            parse_index_daily_bytes(b"0" * (_MAX_RESPONSE + 1), benchmark="NASDAQ_100", as_of="2026-10-01")

    def test_wrong_benchmark_refused_before_get(self):
        with patch.dict(os.environ, GATES):
            out = fetch_index_daily(benchmark="NASDAQ_COMPOSITE", as_of="2026-10-01", api_key=KEY,
                                    explicit_click=True, rights_approved=True, premium_approved=True,
                                    transport=lambda _: self.fail("NETWORK"))
        self.assertEqual(out["requests_attempted"], 0)

    def test_future_date_before_get(self):
        with patch.dict(os.environ, GATES):
            out = fetch_index_daily(benchmark="NASDAQ_100", as_of="2099-01-01", api_key=KEY,
                                    explicit_click=True, rights_approved=True, premium_approved=True,
                                    transport=lambda _: self.fail("NETWORK"))
        self.assertEqual(out["requests_attempted"], 0)

    def test_bad_key_before_get(self):
        with patch.dict(os.environ, GATES):
            out = fetch_index_daily(benchmark="NASDAQ_100", as_of="2026-10-01", api_key="bad&key",
                                    explicit_click=True, rights_approved=True, premium_approved=True,
                                    transport=lambda _: self.fail("NETWORK"))
        self.assertEqual(out["requests_attempted"], 0)

if __name__ == "__main__":
    unittest.main()
