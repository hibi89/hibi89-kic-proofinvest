"""Offline P141 actual parser-to-market-contract and click budget tests.

The full math engine runs in GitHub integration CI; unit tests locally stub
only that downstream call, validating source fields, guards and alignment.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import json
import os
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from proofinvest.market_provider_alpha_vantage import parse_daily_close_bytes
from proofinvest.market_provider_alpha_vantage_index import parse_index_daily_bytes
from proofinvest.market_pair_engine_a import (
    analyze_price_index_pair, build_market_reality_payload,
    fetch_and_analyze_market_pair,
)
from tests.test_market_provider_alpha_vantage_index import sample_index, GATES, KEY

_STOCK_GATES = {"KUODRA_ENABLE_ALPHA_VANTAGE_DAILY": "1", **GATES}


def stock_raw():
    start = date(2026, 7, 1)
    points = {}
    for i in range(140):
        day = start + timedelta(days=i)
        if day.weekday() < 5:
            points[day.isoformat()] = {"4. close": str(100 + i)}
            if len(points) == 65:
                break
    return json.dumps({"Meta Data": {"2. Symbol": "NVDA"},
                       "Time Series (Daily)": points}).encode()


def sources():
    return (parse_daily_close_bytes(stock_raw(), ticker="NVDA", as_of="2026-10-01"),
            parse_index_daily_bytes(sample_index(), benchmark="NASDAQ_100",
                                    as_of="2026-10-01"))


class PairEngineContractTests(unittest.TestCase):
    def make_payload(self, stock=None, index=None, **kwargs):
        a, b = sources()
        return build_market_reality_payload(
            stock=a if stock is None else stock,
            index=b if index is None else index,
            ticker="NVDA", issuer_cik="0001045810", filing_date="2026-06-30",
            as_of="2026-10-01", **kwargs)

    def test_two_real_vendor_schemas_map_to_existing_engine_a(self):
        a = self.make_payload()
        self.assertEqual(a["schema"], "kuodra.market-reality.v1")
        self.assertEqual(a["benchmark"], "NASDAQ_100")
        self.assertEqual(a["return_basis"], "PRICE_ONLY_CLOSE")
        self.assertEqual(len(a["security"]["observations"]), 65)
        self.assertEqual(a["security"]["observations"][0]["date"],
                         a["index"]["observations"][0]["date"])
        self.assertEqual(a["security"]["source"]["provider"],
                         "ALPHA_VANTAGE_RESPONSE_UNVERIFIED")
        self.assertNotIn("apikey", repr(a))

    def test_missing_one_trading_session_must_not_forward_fill(self):
        a, b = sources()
        b["close_observations"].pop(12)
        b["point_count"] -= 1
        b["first_date"] = b["close_observations"][0]["date"]
        b["last_date"] = b["close_observations"][-1]["date"]
        a = self.make_payload(index=b)
        self.assertEqual(len(a["index"]["observations"]), 64)
        self.assertEqual(len(a["security"]["observations"]), 64)

    def test_many_unmatched_sessions_fail_closed(self):
        a, b = sources()
        b["close_observations"] = b["close_observations"][20:]
        b["point_count"] = len(b["close_observations"])
        b["first_date"] = b["close_observations"][0]["date"]
        with self.assertRaises(ValueError):
            self.make_payload(index=b)

    def test_no_lookahead_before_same_day_filing(self):
        a, b = sources()
        with self.assertRaises(ValueError):
            build_market_reality_payload(
                stock=a, index=b, ticker="NVDA", issuer_cik="0001045810",
                filing_date="2026-07-01", as_of="2026-10-01")

    def test_future_session_in_either_receipt_fails_before_ols(self):
        # A single future-only row cannot be silently discarded by the
        # calendar intersection; the date would be a look-ahead leak.
        for role in ("stock", "index"):
            a, b = sources()
            receipt = a if role == "stock" else b
            future = "2026-10-02"
            self.assertLess(receipt["last_date"], future)
            receipt["close_observations"].append(
                {"date": future, "close": "1234"})
            receipt["last_date"] = future
            receipt["point_count"] += 1
            with self.subTest(role=role), self.assertRaisesRegex(
                    ValueError, "FUTURE_PRICE_OBSERVATION"):
                self.make_payload(stock=a, index=b)

    def test_stale_as_of_must_refuse_ols(self):
        a, b = sources()
        a["as_of"] = b["as_of"] = "2026-11-03"
        with self.assertRaises(ValueError):
            build_market_reality_payload(
                stock=a, index=b, ticker="NVDA", issuer_cik="0001045810",
                filing_date="2026-06-30", as_of="2026-11-03")

    def test_other_index_and_etf_mislabeled_are_rejected(self):
        a, b = sources()
        for value in ("QQQ", "SPX", "ETF_QQQ"):
            b2 = deepcopy(b);b2["index_symbol"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.make_payload(index=b2)

    def test_wrong_issuer_ticker_and_benchmark_rejected(self):
        a, b = sources()
        a["ticker"] = "AAPL"
        with self.assertRaises(ValueError):
            self.make_payload(stock=a)
        with self.assertRaises(ValueError):
            self.make_payload(benchmark="NASDAQ_COMPOSITE")

    def test_claimed_rights_or_premium_verified_is_rejected(self):
        for role, field in (("stock", "market_data_rights_verified"),
                            ("index", "source_rights_verified"),
                            ("index", "premium_entitlement_verified"),
                            ("index", "provider_response_authenticated")):
            a, b = sources(); src = a if role == "stock" else b
            src[field] = True
            with self.subTest(role=role, field=field), self.assertRaises(ValueError):
                self.make_payload(stock=a, index=b)

    def test_bad_hash_count_or_date_refused(self):
        for field, value in (("source_sha256", "not-a-digest"),
                             ("point_count", 99), ("last_date", "2026-10-02")):
            a, b = sources();a[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.make_payload(stock=a, index=b)

    def test_engine_a_integration_receives_real_contract_and_returns_redacted(self):
        a, b = sources()
        math = ModuleType("proofinvest.market_reality")
        calls = []
        def analyze(payload, **kwargs):
            calls.append((payload, kwargs))
            return {"status":"REPORTED_UNVERIFIED", "source_authenticated": False,
                    "market_bubble_proven": False,"trade_signal":False,
                    "guard_policy_modified":False,"security_return_pct":"40.0000",
                    "benchmark_return_pct":"5.0000", "beta":"1.2000",
                    "regression_intercept_daily_pct":"0.0100", "r_squared":"0.5500"}
        math.analyze_market_reality = analyze
        with patch.dict(sys.modules, {"proofinvest.market_reality": math}):
            result = analyze_price_index_pair(
                stock=a, index=b, ticker="NVDA", issuer_cik="0001045810",
                filing_date="2026-06-30", as_of="2026-10-01")
        self.assertEqual(result["status"], "ENGINE_A_PRICE_INDEX_DESCRIPTIVE_UNVERIFIED")
        self.assertEqual(result["market_analysis"]["beta"], "1.2000")
        self.assertEqual(result["matched_observation_count"], 65)
        self.assertEqual(result["matched_period_start"],
                         calls[0][0]["index"]["observations"][0]["date"])
        self.assertEqual(result["matched_period_end"],
                         calls[0][0]["index"]["observations"][-1]["date"])
        self.assertLessEqual(result["matched_period_end"], "2026-10-01")
        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0][1]["sec_review"])
        self.assertFalse(result["source_rights_verified"])
        self.assertFalse(result["trade_executed"])

    def test_engine_trust_spoof_is_rejected(self):
        a,b=sources()
        math=ModuleType("proofinvest.market_reality")
        math.analyze_market_reality=lambda *_args,**_kwargs:{"status":"REPORTED_UNVERIFIED",
                        "source_authenticated":True,"market_bubble_proven":False,
                        "trade_signal":False,"guard_policy_modified":False}
        with patch.dict(sys.modules, {"proofinvest.market_reality": math}):
            result=analyze_price_index_pair(stock=a,index=b,ticker="NVDA",
                    issuer_cik="0001045810",filing_date="2026-06-30",as_of="2026-10-01")
        self.assertEqual(result["status"], "BLOCKED")

    def test_preapproved_click_requires_four_independent_gates(self):
        seen=[]
        a,b=sources()
        with patch.dict(os.environ, {}, clear=True):
            r=fetch_and_analyze_market_pair(ticker="NVDA",issuer_cik="0001045810",
                    filing_date="2026-06-30",as_of="2026-10-01",api_key=KEY,
                    explicit_click=True,provider_rights_approved=True,premium_entitlement_approved=True,
                    stock_transport=lambda _: seen.append("stock"),index_transport=lambda _: seen.append("index"))
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(seen,[])

    def test_invalid_premium_ticker_or_asof_before_any_network(self):
        with patch.dict(os.environ,_STOCK_GATES):
            for kw in ({"ticker":"NVDA&evil"},{"as_of":"2099-01-01"},
                       {"filing_date":"2026-10-01"}):
                params=dict(ticker="NVDA",issuer_cik="0001045810",filing_date="2026-06-30",
                        as_of="2026-10-01",api_key=KEY,explicit_click=True,
                        provider_rights_approved=True,premium_entitlement_approved=True,
                        stock_transport=lambda _: self.fail("NETWORK"),
                        index_transport=lambda _: self.fail("NETWORK"))
                params.update(kw)
                with self.subTest(kw=kw):
                    self.assertEqual(fetch_and_analyze_market_pair(**params)["network_requests"],0)

    def test_index_never_fetched_if_stock_provider_fails(self):
        with patch.dict(os.environ,_STOCK_GATES):
            r=fetch_and_analyze_market_pair(ticker="NVDA",issuer_cik="0001045810",
                    filing_date="2026-06-30",as_of="2026-10-01",api_key=KEY,
                    explicit_click=True,provider_rights_approved=True,premium_entitlement_approved=True,
                    stock_transport=lambda _: b'{"Information":"rate limit"}',
                    index_transport=lambda _: self.fail("UNAUTHORIZED_SECOND_CALL"))
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(r["network_requests"],1)

    def test_two_gated_calls_and_backend_output(self):
        math=ModuleType("proofinvest.market_reality")
        math.analyze_market_reality=lambda *_args,**_kwargs:{
            "status":"REPORTED_UNVERIFIED","source_authenticated":False,
            "market_bubble_proven":False,"trade_signal":False,"guard_policy_modified":False,
            "security_return_pct":"40.0000","benchmark_return_pct":"5.0000","beta":"1.2000",
            "regression_intercept_daily_pct":"0.0100","r_squared":"0.5500"}
        with patch.dict(os.environ,_STOCK_GATES), patch.dict(sys.modules,{"proofinvest.market_reality":math}):
            r=fetch_and_analyze_market_pair(ticker="NVDA",issuer_cik="0001045810",
                    filing_date="2026-06-30",as_of="2026-10-01",api_key=KEY,
                    explicit_click=True,provider_rights_approved=True,premium_entitlement_approved=True,
                    stock_transport=lambda _: stock_raw(),index_transport=lambda _: sample_index())
        self.assertEqual(r["status"],"ENGINE_A_PRICE_INDEX_DESCRIPTIVE_UNVERIFIED", r)
        self.assertEqual(r["network_requests"],2)
        self.assertFalse(r["full_a_b_c_ready"])
        self.assertNotIn(KEY,repr(r))

if __name__ == "__main__":
    unittest.main()
