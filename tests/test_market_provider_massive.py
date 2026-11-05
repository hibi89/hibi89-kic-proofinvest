"""P243 Massive $0 Stocks/Indices Basic: offline, genuine NDX, no live GET."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import os
import unittest
from unittest.mock import patch

from proofinvest.market_provider_massive import (
    _https_get, _MAX_RESPONSE, analyze_massive_pair, fetch_massive_pair,
    free_basic_safe_as_of,
    parse_massive_daily,
)

KEY = "SYNTHETICLOCALKEYONLY123"
GATES = {
    "KUODRA_ENABLE_MASSIVE_PAIR": "1",
    "KUODRA_MASSIVE_PERSONAL_RESEARCH_APPROVED": "1",
}


def fixture(symbol="NVDA", count=65, *, index=False, adjusted=False):
    first = date(2026, 7, 1)
    records = []
    for n in range(180):
        d = first + timedelta(days=n)
        if d.weekday() >= 5:
            continue
        ts = int(datetime(d.year, d.month, d.day, 5,
                          tzinfo=timezone.utc).timestamp() * 1000)
        base = Decimal("10000") if index else Decimal("100")
        price = base + Decimal(n) * (Decimal("1.55") if index else Decimal("0.25"))
        records.append({"t": ts, "c": float(price),
                        "o": float(price - 1), "h": float(price + 1),
                        "l": float(price - 1)})
        if len(records) == count:
            break
    obj = {"status": "OK", "ticker": symbol, "results": records,
           "queryCount": len(records), "resultsCount": len(records)}
    if not index:
        obj["adjusted"] = adjusted
    return json.dumps(obj, separators=(",", ":")).encode()


def receipts():
    return (parse_massive_daily(fixture(), symbol="NVDA", as_of="2026-10-01"),
            parse_massive_daily(fixture("I:NDX", index=True),
                                symbol="I:NDX", as_of="2026-10-01", index=True))


class MassiveBasicAdapterTests(unittest.TestCase):
    def test_free_basic_utc_eod_cutoff_weekend_and_dst_independent(self):
        # Conservative UTC-only selection; safe even when Korean morning is
        # still the previous U.S. trading day.
        self.assertEqual(free_basic_safe_as_of(date(2026,11,6)), "2026-11-04")
        self.assertEqual(free_basic_safe_as_of(date(2026,11,7)), "2026-11-05")
        self.assertEqual(free_basic_safe_as_of(date(2026,11,9)), "2026-11-05")
        self.assertEqual(free_basic_safe_as_of(date(2026,11,10)), "2026-11-06")

    def test_free_basic_blocks_unsafe_current_session_before_http(self):
        with patch.dict(os.environ, GATES, clear=True), (
            patch("proofinvest.market_provider_massive.free_basic_safe_as_of",
                  return_value="2026-10-01")):
            result = fetch_massive_pair(
                ticker="NVDA", issuer_cik="0001045810",
                filing_date="2026-07-31", as_of="2026-10-02", api_key=KEY,
                explicit_click=True, individual_research_approved=True,
                stock_transport=lambda _: self.fail("STOCK GET NOT ALLOWED"),
                index_transport=lambda _: self.fail("NDX GET NOT ALLOWED"),
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["network_requests"], 0)

    def test_actual_ndx_symbol_daily_schema_and_eod_bar_math(self):
        a,b = receipts()
        self.assertEqual(a["status"], "DAILY_CLOSE_UNVERIFIED")
        self.assertEqual(b["symbol"], "I:NDX")
        self.assertEqual(b["point_count"], 65)
        self.assertEqual(a["first_date"], "2026-07-01")
        self.assertFalse(a["source_authenticated"])
        self.assertFalse(b["source_rights_verified"])
        self.assertFalse(b["commercial_reuse_allowed"])
        self.assertNotIn("results", b)

    def test_real_decimal_engine_a_with_two_massive_formatted_sources(self):
        stock,ndx=receipts()
        result=analyze_massive_pair(stock=stock, ndx=ndx,
                                    ticker="NVDA", issuer_cik="0001045810",
                                    filing_date="2026-07-31", as_of="2026-10-01")
        self.assertEqual(result["status"], "ENGINE_A_MASSIVE_DESCRIPTIVE_UNVERIFIED",result)
        self.assertEqual(result["matched_observation_count"], 42)
        self.assertEqual(result["matched_period_start"], "2026-08-03")
        self.assertEqual(result["matched_period_end"], "2026-09-29")
        self.assertEqual(result["market_analysis"]["status"], "REPORTED_UNVERIFIED")
        self.assertIsNotNone(result["market_analysis"]["beta"])
        self.assertFalse(result["source_rights_verified"])
        self.assertFalse(result["full_a_b_c_ready"])
        self.assertEqual(result["network_requests"], 0)

    def test_historical_lookahead_and_insufficient_postfiling_still_block(self):
        s,m=receipts()
        for filing in ("2026-08-20", "2026-09-01"):
            with self.subTest(filing=filing):
                o=analyze_massive_pair(stock=s,ndx=m,ticker="NVDA",
                                       issuer_cik="0001045810",
                                       filing_date=filing,as_of="2026-10-01")
                self.assertEqual(o["status"],"BLOCKED")
        o=analyze_massive_pair(stock=s,ndx=m,ticker="AAPL",
                               issuer_cik="0001045810",filing_date="2026-06-30",
                               as_of="2026-10-01")
        self.assertEqual(o["status"],"BLOCKED")

    def test_spoofed_license_or_hash_is_not_promoted(self):
        for role,field,value in (
                ("stock","source_rights_verified",True),
                ("index","commercial_reuse_allowed",True),
                ("index","symbol","I:QQQ"),
                ("stock","source_sha256","bad")):
            a,b=receipts()
            target=a if role=="stock" else b
            target[field]=value
            with self.subTest(role=role,field=field):
                result=analyze_massive_pair(stock=a,ndx=b,ticker="NVDA",
                    issuer_cik="0001045810",filing_date="2026-06-30",as_of="2026-10-01")
                self.assertEqual(result["status"],"BLOCKED")

    def test_critical_provider_errors_block_without_promoting_partial_data(self):
        for raw, symbol, index in (
                (b'{"status":"NOT_AUTHORIZED"}',"I:NDX",True),
                (b'{"status":"ERROR","error":"quota"}',"NVDA",False),
                (fixture("QQQ",index=True),"I:NDX",True),
                (fixture("I:NDX",index=True),"QQQ",True),
                (fixture(adjusted=True),"NVDA",False),
                (fixture(count=30),"NVDA",False),
                (b"invalid-json","NVDA",False),
                (b"0"*(_MAX_RESPONSE+1),"NVDA",False)):
            with self.subTest(symbol=symbol,raw=raw[:40]), self.assertRaises(ValueError):
                parse_massive_daily(raw,symbol=symbol,as_of="2026-10-01",index=index)

    def test_ndx_weekend_future_and_invalid_close_have_separate_codes(self):
        raw = json.loads(fixture("I:NDX", index=True))
        def verify(row, expected):
            data = dict(raw)
            data["results"] = [dict(x) for x in raw["results"]]
            data["results"][0] = dict(row)
            with self.assertRaisesRegex(ValueError, "^" + expected + "$"):
                parse_massive_daily(json.dumps(data).encode(), symbol="I:NDX",
                                    as_of="2026-10-01", index=True)
        weekend = dict(raw["results"][0])
        weekend["t"] = int(datetime(2026,7,4,5,tzinfo=timezone.utc).timestamp()*1000)
        verify(weekend,"NONTRADING_WEEKEND_BAR")
        future = dict(raw["results"][0])
        future["t"] = int(datetime(2026,10,2,5,tzinfo=timezone.utc).timestamp()*1000)
        verify(future,"BAR_AFTER_REQUESTED_CUTOFF")
        negative = dict(raw["results"][0])
        negative["c"] = -1
        verify(negative,"CLOSE_OUT_OF_BOUNDS")

    def test_duplicate_bar_calendar_and_nonfinite_close_are_blocked(self):
        raw=json.loads(fixture())
        raw["results"].append(raw["results"][-1])
        raw["resultsCount"] += 1
        raw["queryCount"] += 1
        with self.assertRaises(ValueError):
            parse_massive_daily(json.dumps(raw).encode(),
                                 symbol="NVDA",as_of="2026-10-01")
        raw=json.loads(fixture())
        raw["results"][0]["c"]=-10
        with self.assertRaises(ValueError):
            parse_massive_daily(json.dumps(raw).encode(),symbol="NVDA",as_of="2026-10-01")
        raw=json.loads(fixture())
        raw["results"][0]["t"]+=86400000*300
        with self.assertRaises(ValueError):
            parse_massive_daily(json.dumps(raw).encode(),symbol="NVDA",as_of="2026-10-01")
        duplicate=b'{"status":"OK","ticker":"NVDA","ticker":"AAPL","results":[]}'
        with self.assertRaises(ValueError):
            parse_massive_daily(duplicate,symbol="NVDA",as_of="2026-10-01")

    def test_no_auto_network_without_independent_gates(self):
        calls=[]
        for env, kw in (
            ({},dict(explicit_click=True,individual_research_approved=True)),
            (GATES,dict()),
            (GATES,dict(explicit_click=True)),
            (GATES,dict(individual_research_approved=True))):
            with patch.dict(os.environ,env,clear=True):
                out=fetch_massive_pair(ticker="NVDA",issuer_cik="0001045810",
                     filing_date="2026-06-30",as_of="2026-10-01",api_key=KEY,
                     stock_transport=lambda _: calls.append("s"),
                     index_transport=lambda _: calls.append("i"),**kw)
                self.assertEqual(out["network_requests"],0)
                self.assertEqual(out["status"],"BLOCKED")
        self.assertEqual(calls,[])

    def test_forged_bad_identity_future_and_key_block_pre_network(self):
        with patch.dict(os.environ,GATES,clear=True):
            for kw in ({"ticker":"NVDA/../../x"},{"ticker":"I:NDX"},
                       {"api_key":"oops&apikey=evil"},{"issuer_cik":"0000000000"},
                       {"as_of":"2099-12-01"},{"filing_date":"2026-10-01"}):
                params=dict(ticker="NVDA",issuer_cik="0001045810",
                            filing_date="2026-06-30",as_of="2026-10-01",
                            api_key=KEY,explicit_click=True,
                            individual_research_approved=True,
                            stock_transport=lambda _:self.fail("UNAUTHORIZED HTTP"),
                            index_transport=lambda _:self.fail("UNAUTHORIZED HTTP"))
                params.update(kw)
                with self.subTest(kw=kw):
                    o=fetch_massive_pair(**params)
                    self.assertEqual(o["network_requests"],0)

    def test_exact_stock_ndx_urls_bounded_calls_no_key_leak(self):
        calls=[]
        def stock(url):
            calls.append(url)
            return fixture()
        def index(url):
            calls.append(url)
            return fixture("I:NDX",index=True)
        with patch.dict(os.environ,GATES,clear=True):
            r=fetch_massive_pair(ticker="NVDA",issuer_cik="0001045810",
              filing_date="2026-07-31",as_of="2026-10-01",api_key=KEY,
              explicit_click=True,individual_research_approved=True,
              stock_transport=stock,index_transport=index)
        self.assertEqual(r["status"],"ENGINE_A_MASSIVE_DESCRIPTIVE_UNVERIFIED",r)
        self.assertEqual(r["network_requests"],2)
        self.assertEqual(len(calls),2)
        self.assertIn("/ticker/NVDA/range/1/day/",calls[0])
        self.assertIn("/ticker/I:NDX/range/1/day/",calls[1])
        self.assertIn("adjusted=false",calls[0])
        self.assertNotIn("adjusted=",calls[1])
        self.assertNotIn(KEY,repr(r))
        self.assertNotIn("apiKey",repr(r))

    def test_stock_fails_and_ndx_not_requested(self):
        with patch.dict(os.environ,GATES,clear=True):
            o=fetch_massive_pair(ticker="NVDA",issuer_cik="0001045810",
              filing_date="2026-06-30",as_of="2026-10-01",api_key=KEY,
              explicit_click=True,individual_research_approved=True,
              stock_transport=lambda _:b'{"status":"ERROR"}',
              index_transport=lambda _:self.fail("NDX REQUEST MUST NOT RUN"))
        self.assertEqual(o["status"],"BLOCKED")
        self.assertEqual(o["network_requests"],1)

    def test_no_proxy_no_redirect_bounded_get(self):
        import proofinvest.market_provider_massive as mod
        from urllib.request import ProxyHandler
        url="https://api.massive.com/v2/aggs/ticker/NVDA/range/1/day/2026-07-01/2026-10-01"
        class Response:
            status=200
            def geturl(self): return url
            def read(self,cap):
                self_cap=cap
                self_limit=_MAX_RESPONSE+1
                if self_cap!=self_limit:
                    raise AssertionError("READ NOT BOUNDED")
                return b"{}"
            def __enter__(self): return self
            def __exit__(self,*args): return False
        class Opener:
            def open(self,request,timeout):
                self_url=request.full_url
                if self_url!=url or timeout!=8:
                    raise AssertionError("BAD REQUEST")
                return Response()
        def build(*handlers):
            self.assertEqual([x.proxies for x in handlers if isinstance(x,ProxyHandler)],[{}])
            self.assertTrue(any(isinstance(x,mod._NoRedirect) for x in handlers))
            return Opener()
        with patch.object(mod,"build_opener",side_effect=build),patch.dict(os.environ,{
            "HTTPS_PROXY":"http://attacker.invalid:3333"}):
            self.assertEqual(_https_get(url),b"{}")

if __name__ == "__main__":
    unittest.main()
