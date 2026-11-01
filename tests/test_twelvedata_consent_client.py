"""P110 consent and exact-budget live transport isolated via injected fake IO."""
from __future__ import annotations

from datetime import date, timedelta
import json
import os
from unittest.mock import patch
import unittest

from proofinvest import twelvedata_consent_client as cli
from tests.test_twelvedata_offline_adapter import _fixtures, _raw


def dates():
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=76)
    return {"start_date": start.isoformat(), "end_date": end.isoformat(),
            "as_of": date.today().isoformat()}


class FakeResponse:
    def __init__(self, payload: bytes, status=200, left="6"):
        self.payload = payload
        self.status = status
        self.headers = {"api-credits-left": left}
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, count):
        return self.payload[:count]


def series_pair():
    # Private synthetic rows for today-relative test; real IO never executes.
    stock, index = _fixtures()
    # Generate 45 valid weekday sessions spanning the last ~75 calendar days.
    end = date.today() - timedelta(days=1)
    days = []
    point = end
    while len(days) < 45:
        if point.weekday() < 5:
            days.append(point.isoformat())
        point -= timedelta(days=1)
    for row, day in zip(stock["values"], days):
        row["datetime"] = day
    for row, day in zip(index["values"], days):
        row["datetime"] = day
    return _raw(stock), _raw(index)


class ConsentClientTests(unittest.TestCase):
    def test_default_disabled_zero_calls_even_with_transport(self):
        calls = []
        def transport(*args):
            calls.append(args)
            raise AssertionError("NETWORK_NOT_APPROVED")
        r = cli.run_approved_internal_pair(
            **dates(), opener=transport,
            index_entitlement_confirmed=True, internal_test_rights_confirmed=True)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertEqual(r["requests_attempted"], 0)
        self.assertEqual(calls, [])

    def test_plan_eligibility_and_no_secret_in_public_plan(self):
        blocked = cli.make_request_plan(**dates())
        self.assertEqual(blocked["planned_gets"], 0)
        ready = cli.make_request_plan(
            **dates(), index_entitlement_confirmed=True,
            internal_test_rights_confirmed=True)
        self.assertEqual(ready["planned_gets"], 2)
        self.assertEqual(ready["estimated_standard_time_series_credits"], 2)
        self.assertTrue(all("apikey" not in u for u in ready["urls_without_keys"]))
        self.assertTrue(all(u.startswith(cli._ORIGIN+"?") for u in ready["urls_without_keys"]))
        self.assertFalse(ready["license_independently_verified"])
        self.assertFalse(ready["index_symbol_entitlement_independently_verified"])

    def test_historical_as_of_cannot_impersonate_point_in_time_retrieval(self):
        old = {"start_date": "2025-08-01", "end_date": "2025-10-15",
               "as_of": "2025-10-16"}
        self.assertEqual(cli.make_request_plan(
            **old, index_entitlement_confirmed=True,
            internal_test_rights_confirmed=True)["planned_gets"], 0)

    def test_bad_index_symbol_or_short_window_blocks(self):
        opts = dates()
        for change in ({"index_symbol": "QQQ"},
                       {"start_date": opts["end_date"]},
                       {"end_date": "2100-01-01"}):
            with self.subTest(change=change):
                r = cli.make_request_plan(
                    **{**opts, **change}, index_entitlement_confirmed=True,
                    internal_test_rights_confirmed=True)
                self.assertEqual(r["planned_gets"], 0)

    def test_no_key_never_creates_http(self):
        with patch.dict(os.environ, {"KUODRA_TWELVEDATA_API_KEY": ""}):
            r = cli.run_approved_internal_pair(
                **dates(), index_entitlement_confirmed=True,
                internal_test_rights_confirmed=True,
                allow_network=True, acknowledge_exactly_two_gets=True)
        self.assertEqual(r["requests_attempted"], 0)
        self.assertEqual(r["reason_code"], "LOCAL_API_KEY_MISSING_OR_INVALID")

    def test_two_mock_requests_header_only_not_url_and_p108_math(self):
        pair = series_pair()
        calls = []
        def transport(req, timeout):
            calls.append(req)
            self.assertEqual(timeout, 8.0)
            self.assertNotIn("apikey", req.full_url)
            self.assertEqual(req.get_header("Authorization"), "apikey SECRET_TEST_TOKEN_1234")
            return FakeResponse(pair[len(calls)-1])
        r = cli.run_approved_internal_pair(
            **dates(), api_key="SECRET_TEST_TOKEN_1234",
            index_entitlement_confirmed=True, internal_test_rights_confirmed=True,
            allow_network=True, acknowledge_exactly_two_gets=True,
            opener=transport)
        self.assertEqual(len(calls), 2)
        self.assertEqual(r["requests_attempted"], 2)
        self.assertEqual(r["status"], "INTERNAL_OFFLINE_ARITHMETIC_UNVERIFIED", r)
        self.assertEqual(r["analysis"]["analysis"]["engine_a"]["status"], "REPORTED_UNVERIFIED")
        self.assertEqual(r["analysis"]["guard_decision"], "HOLD")
        self.assertNotIn("SECRET_TEST_TOKEN_1234", json.dumps(r))
        self.assertFalse(r["source_authenticated"])
        self.assertFalse(r["commercial_use_authorized"])

    def test_first_http_403_429_302_or_out_of_credits_never_calls_second(self):
        stock, _ = series_pair()
        for status, left in ((403, "7"), (429, "7"), (302, "7"), (200, "0")):
            calls = []
            def transport(*_):
                calls.append(1)
                return FakeResponse(stock, status=status, left=left)
            r = cli.run_approved_internal_pair(
                **dates(), api_key="SECRET_TEST_TOKEN_1234",
                index_entitlement_confirmed=True, internal_test_rights_confirmed=True,
                allow_network=True, acknowledge_exactly_two_gets=True,
                opener=transport)
            self.assertEqual(r["status"], "BLOCKED")
            self.assertEqual(r["requests_attempted"], 1)
            self.assertEqual(len(calls), 1)

    def test_invalid_first_response_stops_without_second_and_no_raw_echo(self):
        for raw in (b'{"status":"error","message":"invalid apikey secret"}',
                    b"notjson", b"x" * (cli.MAX_RESPONSE_BYTES+1)):
            calls = []
            def transport(*_):
                calls.append(True)
                return FakeResponse(raw)
            r = cli.run_approved_internal_pair(
                **dates(), api_key="SECRET_TEST_TOKEN_1234",
                index_entitlement_confirmed=True, internal_test_rights_confirmed=True,
                allow_network=True, acknowledge_exactly_two_gets=True,
                opener=transport)
            self.assertEqual(len(calls), 1)
            self.assertEqual(r["requests_attempted"], 1)
            self.assertNotIn("invalid apikey secret", json.dumps(r))
            self.assertNotIn("SECRET_TEST_TOKEN_1234", json.dumps(r))

    def test_malformed_nvda_metadata_and_price_never_spend_ndx_credit(self):
        stock, index = series_pair()
        baseline = json.loads(stock)
        bad_cases = {}
        for name, field, value in (
            ("etf_spoof", "type", "ETF"),
            ("wrong_currency", "currency", "EUR"),
            ("wrong_timezone", "exchange_timezone", "Etc/UTC"),
            ("weekly_data", "interval", "1week"),
            ("wrong_ticker", "symbol", "AAPL"),
        ):
            data = json.loads(stock)
            data["meta"][field] = value
            bad_cases[name] = json.dumps(data).encode()
        for name, value in (
            ("zero_close", "0"),
            ("negative_close", "-2"),
            ("nonfinite_close", "NaN"),
            ("excel_formula", "=1+1"),
        ):
            data = json.loads(stock)
            data["values"][0]["close"] = value
            bad_cases[name] = json.dumps(data).encode()
        data = json.loads(stock)
        data["values"][1]["datetime"] = data["values"][0]["datetime"]
        bad_cases["duplicate_day"] = json.dumps(data).encode()
        data = json.loads(stock)
        data["values"].reverse()
        bad_cases["ascending_days"] = json.dumps(data).encode()
        data = json.loads(stock)
        data["values"][1]["datetime"] = "2025-02-25"
        bad_cases["before_issuer_release"] = json.dumps(data).encode()
        bad_cases["duplicate_json_key"] = stock.replace(
            b'"status":"ok"', b'"status":"ok","status":"ok"', 1
        )
        for name, malformed in bad_cases.items():
            calls = []
            def transport(*_):
                calls.append(True)
                return FakeResponse(malformed if len(calls) == 1 else index)
            with self.subTest(name=name):
                r = cli.run_approved_internal_pair(
                    **dates(), api_key="SECRET_TEST_TOKEN_1234",
                    index_entitlement_confirmed=True,
                    internal_test_rights_confirmed=True,
                    allow_network=True, acknowledge_exactly_two_gets=True,
                    opener=transport,
                )
                self.assertEqual(r["status"], "BLOCKED")
                self.assertEqual(r["requests_attempted"], 1, r)
                self.assertEqual(len(calls), 1, r)
                self.assertEqual(r["reason_code"],
                                 "PROVIDER_RESPONSE_IDENTITY_OR_WINDOW_REJECTED")
                self.assertIsNone(r["analysis"])
                self.assertNotIn("SECRET_TEST_TOKEN_1234", json.dumps(r))

    def test_second_index_etf_or_currency_conflict_yields_no_partial_analysis(self):
        stock, index = series_pair()
        for modification in ("ETF", "QQQ", "wrong_close"):
            broken = json.loads(index)
            if modification == "ETF":
                broken["meta"]["type"] = "ETF"
            elif modification == "QQQ":
                broken["meta"]["symbol"] = "QQQ"
            else:
                broken["values"][0]["close"] = "-1"
            calls = []
            def transport(*_):
                calls.append(True)
                return FakeResponse(
                    stock if len(calls) == 1 else json.dumps(broken).encode()
                )
            with self.subTest(modification=modification):
                r = cli.run_approved_internal_pair(
                    **dates(), api_key="SECRET_TEST_TOKEN_1234",
                    index_entitlement_confirmed=True,
                    internal_test_rights_confirmed=True,
                    allow_network=True, acknowledge_exactly_two_gets=True,
                    opener=transport,
                )
                self.assertEqual(r["requests_attempted"], 2)
                self.assertEqual(r["status"], "BLOCKED")
                self.assertIsNone(r["analysis"])
                self.assertEqual(r["guard_decision"], "HOLD")

    def test_partial_first_response_never_fabricates_real_data(self):
        stock, _ = series_pair()
        r = cli.run_approved_internal_pair(
            **dates(), api_key="SECRET_TEST_TOKEN_1234",
            index_entitlement_confirmed=True, internal_test_rights_confirmed=True,
            allow_network=True, acknowledge_exactly_two_gets=True,
            opener=lambda *_: FakeResponse(stock))
        self.assertEqual(r["status"], "BLOCKED")
        self.assertEqual(r["requests_attempted"], 2)
        self.assertIsNone(r["analysis"])
        self.assertEqual(r["guard_decision"], "HOLD")


if __name__ == "__main__":
    unittest.main()
