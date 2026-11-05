"""No network: deterministic Alpha Vantage daily-source contract tests."""
from __future__ import annotations

from datetime import date, timedelta
import json
import os
import unittest
from unittest.mock import patch

from proofinvest.market_provider_alpha_vantage import (
    fetch_daily_close, parse_daily_close_bytes,
)

KEY = "DEMOFAKEKEY123456"
GATES = {"KUODRA_ENABLE_ALPHA_VANTAGE_DAILY": "1",
         "KUODRA_ALPHA_VANTAGE_RIGHTS_APPROVED": "1"}


def fixture(symbol="AAPL", count=65):
    points = {}
    start = date(2026, 7, 1)
    for index in range(200):
        day = start + timedelta(days=index)
        if day.weekday() < 5:
            points[day.isoformat()] = {"4. close": str(100 + index)}
            if len(points) == count:
                break
    return json.dumps({"Meta Data": {"2. Symbol": symbol},
                       "Time Series (Daily)": points}).encode()


class AlphaVantageContractTests(unittest.TestCase):
    def test_key_bearing_https_opener_ignores_ambient_proxy_settings(self):
        # Transport construction only: no paid API key and no actual HTTP.
        import proofinvest.market_provider_alpha_vantage as provider
        from urllib.request import ProxyHandler
        url = "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY"
        calls = []
        class FakeResponse:
            status = 200
            def geturl(self):
                return url
            def read(self, limit):
                self_limit = provider._MAX_BODY + 1
                if limit != self_limit:
                    raise AssertionError("INVALID_READ_BOUND")
                return b'{}'
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
        class FakeOpener:
            def open(self, request, timeout):
                self_url = request.full_url
                if self_url != url or timeout != 8:
                    raise AssertionError("WRONG_URL_OR_TIMEOUT")
                calls.append(1)
                return FakeResponse()
        def fake_build(*handlers):
            proxies = [h.proxies for h in handlers if isinstance(h, ProxyHandler)]
            self.assertEqual(proxies, [{}])
            self.assertTrue(any(isinstance(h, provider._NoRedirect) for h in handlers))
            return FakeOpener()
        with patch.object(provider, "build_opener", side_effect=fake_build), (
            patch.dict(os.environ, {"HTTPS_PROXY":"http://attacker.invalid:9999"})):
            self.assertEqual(provider._https_get(url), b'{}')
        self.assertEqual(calls, [1])

    def test_positive_strict_daily_parser(self):
        out = parse_daily_close_bytes(fixture(), ticker="AAPL", as_of="2026-11-03")
        self.assertEqual(out["status"], "PRICE_ONLY_UNVERIFIED")
        self.assertEqual(out["point_count"], 65)
        self.assertEqual(out["basis"], "PRICE_ONLY_CLOSE")
        self.assertFalse(out["market_data_rights_verified"])
        self.assertFalse(out["full_a_b_c_ready"])

    def test_no_approval_means_no_request_even_with_transport(self):
        with patch.dict(os.environ, GATES):
            for kw in ({}, {"explicit_click": True}, {"rights_approved": True}):
                with self.subTest(kw=kw):
                    out = fetch_daily_close(ticker="AAPL", as_of="2026-11-03",
                                            api_key=KEY, transport=lambda _: self.fail("NETWORK"), **kw)
                    self.assertEqual(out["requests_attempted"], 0)

    def test_disabled_env_means_no_request(self):
        with patch.dict(os.environ, {}, clear=True):
            out = fetch_daily_close(ticker="AAPL", as_of="2026-11-03", api_key=KEY,
                                    explicit_click=True, rights_approved=True,
                                    transport=lambda _: self.fail("NETWORK"))
            self.assertEqual(out["requests_attempted"], 0)

    def test_exactly_one_approved_request_with_no_key_in_output(self):
        seen = []
        with patch.dict(os.environ, GATES):
            result = fetch_daily_close(ticker="AAPL", as_of="2026-11-03", api_key=KEY,
                                       explicit_click=True, rights_approved=True,
                                       transport=lambda url: (seen.append(url), fixture())[1])
        self.assertEqual(len(seen), 1)
        self.assertIn("TIME_SERIES_DAILY", seen[0])
        self.assertEqual(result["requests_attempted"], 1)
        self.assertEqual(result["status"], "PRICE_ONLY_UNVERIFIED")
        self.assertNotIn(KEY, json.dumps(result))
        self.assertNotIn("apikey=", json.dumps(result))

    def test_error_does_not_leak_key_or_retry(self):
        seen = []
        def failure(url):
            seen.append(url)
            raise OSError(f"URL has key={KEY}")
        with patch.dict(os.environ, GATES):
            r = fetch_daily_close(ticker="AAPL", as_of="2026-11-03", api_key=KEY,
                                  explicit_click=True, rights_approved=True, transport=failure)
        self.assertEqual(len(seen), 1)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertEqual(r["requests_attempted"], 1)
        self.assertNotIn(KEY, json.dumps(r))

    def test_provider_quota_notice_blocks(self):
        with self.assertRaises(ValueError):
            parse_daily_close_bytes(b'{"Note":"limit"}', ticker="AAPL", as_of="2026-11-03")

    def test_forged_other_symbol_blocks(self):
        with self.assertRaises(ValueError):
            parse_daily_close_bytes(fixture("MSFT"), ticker="AAPL", as_of="2026-11-03")

    def test_duplicate_root_keys_block(self):
        raw = fixture()
        raw = raw.replace(b'"Meta Data":', b'"Meta Data": {"2. Symbol": "AAPL"}, "Meta Data":', 1)
        with self.assertRaises(ValueError):
            parse_daily_close_bytes(raw, ticker="AAPL", as_of="2026-11-03")

    def test_bad_close_blocks(self):
        raw = fixture().replace(b'"4. close": "100"', b'"4. close": "nan"')
        with self.assertRaises(ValueError):
            parse_daily_close_bytes(raw, ticker="AAPL", as_of="2026-11-03")

    def test_fewer_than_31_points_blocks(self):
        with self.assertRaises(ValueError):
            parse_daily_close_bytes(fixture(count=30), ticker="AAPL", as_of="2026-11-03")

    def test_future_as_of_no_network(self):
        with patch.dict(os.environ, GATES):
            r = fetch_daily_close(ticker="AAPL", as_of="2099-01-01", api_key=KEY,
                                  explicit_click=True, rights_approved=True,
                                  transport=lambda _: self.fail("NETWORK"))
        self.assertEqual(r["requests_attempted"], 0)

    def test_symbol_injection_no_network(self):
        with patch.dict(os.environ, GATES):
            r = fetch_daily_close(ticker="AAPL&apikey=ATTACK", as_of="2026-11-03", api_key=KEY,
                                  explicit_click=True, rights_approved=True,
                                  transport=lambda _: self.fail("NETWORK"))
        self.assertEqual(r["requests_attempted"], 0)


if __name__ == "__main__":
    unittest.main()
