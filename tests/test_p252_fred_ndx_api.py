"""P252 FRED one-shot genuine NASDAQ100 API contract (mocked, no HTTP)."""
from __future__ import annotations

from datetime import date, timedelta
from io import StringIO
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from proofinvest import market_provider_fred_api as api
from scripts import p252_fred_ndx_api_probe as cli
from tests.test_fred_nasdaq100_offline import fred_data, AS_OF

KEY = "abcdef0123456789abcdef0123456789"


def wire(*, as_of=AS_OF):
    dates = fred_data().decode().splitlines()[1:]
    day = date.fromisoformat(as_of)
    obs = [
        {"realtime_start": as_of, "realtime_end": as_of,
         "date": d, "value": v}
        for d,v in (line.split(",") for line in dates)
    ]
    return json.dumps({
        "realtime_start": as_of, "realtime_end": as_of,
        "observation_start": (day - timedelta(days=190)).isoformat(),
        "observation_end": as_of, "units": "lin",
        "output_type": 1, "file_type": "json", "sort_order": "asc",
        "count": len(obs), "offset": 0, "limit": 200,
        "observations": obs,
    },separators=(",", ":")).encode()


class FredApiOneShotTests(unittest.TestCase):
    def test_official_url_is_pinned_to_true_index_daily_raw_point_in_time(self):
        url = api._url(api_key=KEY, as_of=AS_OF)
        self.assertTrue(url.startswith("https://api.stlouisfed.org/fred/series/observations?"))
        for term in ("series_id=NASDAQ100", "file_type=json",
                     "units=lin", "sort_order=asc", "observation_end="+AS_OF,
                     "realtime_start="+AS_OF, "realtime_end="+AS_OF,
                     "limit=200"):
            self.assertIn(term,url)
        self.assertNotIn("QQQ",url)
        self.assertNotIn("I%3ANDX",url)

    def test_real_parser_uses_existing_strict_csv_calendar_without_origin_promotion(self):
        receipt=api.parse_fred_nasdaq100_api_json(wire(),as_of=AS_OF)
        self.assertEqual(receipt["status"],"FRED_API_DAILY_PARSED_ORIGIN_AND_RIGHTS_UNVERIFIED")
        self.assertEqual(receipt["series_id"],"NASDAQ100")
        self.assertEqual(receipt["index_symbol"],"I:NDX")
        self.assertEqual(receipt["point_count"],65)
        self.assertEqual(receipt["first_date"],"2026-07-01")
        self.assertEqual(receipt["last_date"],"2026-09-29")
        for key in ("source_authenticated","source_rights_verified",
                    "public_display_allowed","commercial_reuse_allowed",
                    "ai_processing_allowed","trade_executed"):
            self.assertFalse(receipt[key])
        self.assertEqual(len(receipt["source_sha256"]),64)

    def test_no_approval_or_bad_key_cannot_issue_get(self):
        for a,individual,key in ((False,True,KEY),(True,False,KEY),
                                 (True,True,"bad key")):
            with self.subTest(a=a,individual=individual,key=key),(
                patch.object(api, "_get",side_effect=AssertionError("NO NETWORK"))):
                x=api.run_one_fred_ndx_get(api_key=key,as_of=AS_OF,
                                           explicit_approval=a,individual_research=individual)
                self.assertEqual(x["status"],"BLOCKED")
                self.assertEqual(x["network_requests"],0)

    def test_owner_approved_one_get_sanitized_success(self):
        calls=[]
        def mock(url):
            calls.append(url)
            return wire()
        x=api.run_one_fred_ndx_get(api_key=KEY,as_of=AS_OF,
                                  explicit_approval=True,individual_research=True,
                                  transport=mock)
        self.assertEqual(len(calls),1)
        self.assertEqual(x["network_requests"],1)
        self.assertEqual(x["retries"],0)
        self.assertEqual(x["point_count"],65)
        self.assertEqual(x["status"],"FRED_API_DAILY_PARSED_ORIGIN_AND_RIGHTS_UNVERIFIED")
        self.assertFalse(x["market_data_rights_verified"])
        self.assertFalse(x["source_authenticated"])
        self.assertNotIn(KEY,json.dumps(x))
        self.assertNotIn("close_observations",x)

    def test_bad_vintage_and_wrong_units_rejected(self):
        for key,bad in (("realtime_start","2026-11-01"),
                        ("observation_end","2026-10-02"),
                        ("units","pc1"),("file_type","csv"),
                        ("output_type",3),("sort_order","desc")):
            x=json.loads(wire());x[key]=bad
            with self.subTest(key=key),self.assertRaisesRegex(
                    ValueError,"FRED_RESPONSE_CONTRACT_INVALID|FRED_OBSERVATION_WINDOW_INVALID"):
                api.parse_fred_nasdaq100_api_json(json.dumps(x).encode(),as_of=AS_OF)

    def test_unexpected_weekend_price_is_rejected_not_shifted(self):
        x=json.loads(wire())
        x["observations"][2]["date"]="2026-07-04"
        with self.assertRaisesRegex(ValueError,"WEEKEND_DAILY_PRICE"):
            api.parse_fred_nasdaq100_api_json(json.dumps(x).encode(),as_of=AS_OF)

    def test_fred_missing_value_never_forward_filled(self):
        x=json.loads(wire());x["observations"][5]["value"]="."
        result=api.parse_fred_nasdaq100_api_json(json.dumps(x).encode(),as_of=AS_OF)
        self.assertEqual(result["point_count"],64)
        self.assertEqual(result["missing_rows_ignored"],1)

    def test_duplicate_payload_json_key_and_pagination_rejected(self):
        orig=wire()
        doubled=orig.replace(b'"observations":',b'"observations":[],"observations":',1)
        with self.assertRaisesRegex(ValueError,"FRED_DUPLICATE_JSON_KEY"):
            api.parse_fred_nasdaq100_api_json(doubled,as_of=AS_OF)
        x=json.loads(orig);x["limit"]=1
        with self.assertRaisesRegex(ValueError,"FRED_PAGINATION_UNAVAILABLE"):
            api.parse_fred_nasdaq100_api_json(json.dumps(x).encode(),as_of=AS_OF)

    def test_response_error_and_oversized_are_rejected(self):
        for payload in (b'{"error_code":429,"error_message":"quota"}',
                        b"\x00"*1024, b"z"*262145):
            with self.subTest(sz=len(payload)),self.assertRaises(ValueError):
                api.parse_fred_nasdaq100_api_json(payload,as_of=AS_OF)

    def test_http_429_one_attempt_no_retry_and_no_secret(self):
        calls=[]
        def error(url):
            calls.append(url)
            raise HTTPError(url,429,"some sensitive response",None,None)
        result=api.run_one_fred_ndx_get(
            api_key=KEY,as_of=AS_OF,individual_research=True,
            explicit_approval=True,transport=error)
        self.assertEqual(len(calls),1)
        self.assertEqual(result["reason_code"],"FRED_RATE_LIMITED")
        self.assertEqual(result["network_requests"],1)
        self.assertEqual(result["retries"],0)
        self.assertNotIn(KEY,str(result))

    def test_cli_dry_run_zero_get(self):
        output=[]
        with patch.object(cli,"_safe_date",return_value=AS_OF),(
            patch.object(api,"_get",side_effect=AssertionError("NO HTTP"))),(
            patch("builtins.print",side_effect=lambda *a,**k: output.append(
                " ".join(map(str,a))))):
            result=cli.main([])
        self.assertEqual(result,0)
        x=json.loads(output[-1])
        self.assertEqual(x["status"],"DRY_RUN_NO_REQUEST")
        self.assertEqual(x["network_requests"],0)

    def test_cli_no_tty_blocks_before_key_or_get(self):
        output=[]
        with patch.object(cli,"_safe_date",return_value=AS_OF),(
            patch.object(cli.sys.stdin,"isatty",return_value=False)),(
            patch.object(cli.getpass,"getpass",side_effect=AssertionError("KEY"))),(
            patch.object(api,"_get",side_effect=AssertionError("HTTP"))),(
            patch("builtins.print",side_effect=lambda *a,**k: output.append(
                " ".join(map(str,a))))):
            rc=cli.main(["--live"])
        self.assertEqual(rc,2)
        self.assertEqual(json.loads(output[-1])["reason_code"],"REAL_TTY_REQUIRED")

    def test_cli_one_local_hidden_key_and_success_receipt(self):
        out=[]
        with patch.object(cli,"_safe_date",return_value=AS_OF),(
            patch.object(cli.sys.stdin,"isatty",return_value=True)),(
            patch.object(cli.sys.stdout,"isatty",return_value=True)),(
            patch("builtins.input",return_value=cli._APPROVAL)),(
            patch.object(cli.getpass,"getpass",return_value=KEY)),(
            patch.object(api,"_get",return_value=wire())) as req,(
            patch("builtins.print",side_effect=lambda *a,**k: out.append(
                " ".join(map(str,a))))):
            rc=cli.main(["--live"])
        self.assertEqual(rc,0)
        req.assert_called_once()
        result=json.loads(out[-1])
        self.assertEqual(result["point_count"],65)
        self.assertEqual(result["network_requests"],1)
        self.assertNotIn(KEY,str(out))

    def test_cli_declined_owner_consent_no_get(self):
        out=[]
        with patch.object(cli,"_safe_date",return_value=AS_OF),(
            patch.object(cli.sys.stdin,"isatty",return_value=True)),(
            patch.object(cli.sys.stdout,"isatty",return_value=True)),(
            patch("builtins.input",return_value="NO")),(
            patch.object(cli.getpass,"getpass",side_effect=AssertionError("KEY"))),(
            patch.object(api,"_get",side_effect=AssertionError("GET"))),(
            patch("builtins.print",side_effect=lambda *a,**k: out.append(
                " ".join(map(str,a))))):
            rc=cli.main(["--live"])
        self.assertEqual(rc,2)
        self.assertEqual(json.loads(out[-1])["reason_code"],"OWNER_DECLINED")


class FredApiOneShotPairTests(unittest.TestCase):
    """Local stock and a single FRED v1 JSON response share one Engine A run."""

    def stock(self):
        from proofinvest.fred_nasdaq100_offline import parse_owner_stock_csv
        from tests.test_fred_nasdaq100_offline import stock_data, SOURCE
        return parse_owner_stock_csv(stock_data(), ticker="AAPL",
                                     as_of=AS_OF, source_url=SOURCE)

    def run_pair(self, **changes):
        opts=dict(api_key=KEY, as_of=AS_OF, explicit_approval=True,
                  individual_research=True, paired_stock=self.stock(),
                  paired_ticker="AAPL", paired_issuer_cik="0000320193",
                  paired_filing_date="2026-07-31",
                  transport=lambda _: wire())
        opts.update(changes)
        return api.run_one_fred_ndx_get(**opts)

    def test_actual_decimal_market_pair_in_same_approved_get(self):
        calls=[]
        result=self.run_pair(transport=lambda url:(calls.append(url),wire())[1])
        self.assertEqual(len(calls),1)
        self.assertEqual(result["network_requests"],1)
        self.assertEqual(result["retries"],0)
        a=result["paired_engine_a"]
        self.assertEqual(a["status"],"FRED_API_ENGINE_A_DESCRIPTIVE_UNVERIFIED",a)
        self.assertEqual(a["matched_observation_count"],42)
        self.assertIsNotNone(a["market_analysis"]["beta"])
        self.assertFalse(a["source_rights_verified"])
        self.assertFalse(a["full_a_b_c_ready"])
        self.assertNotIn(KEY,json.dumps(result))
        self.assertNotIn("close_observations",json.dumps(result))

    def test_permission_and_bad_stock_block_before_get(self):
        for changed in ({"explicit_approval":False},
                        {"paired_ticker":"MSFT"},
                        {"paired_issuer_cik":"0000000000"},
                        {"paired_filing_date":"2026-10-01"}):
            calls=[]
            result=self.run_pair(transport=lambda url:calls.append(url),**changed)
            self.assertEqual(calls,[])
            self.assertEqual(result["network_requests"],0)
        stock=self.stock();stock["ai_processing_allowed"]=True
        result=self.run_pair(paired_stock=stock,
                             transport=lambda _:self.fail("GET"))
        self.assertEqual(result["reason_code"],"FRED_PAIR_LOCAL_INPUT_INVALID")

    def test_late_filing_rejects_pair_without_second_request(self):
        calls=[]
        result=self.run_pair(paired_filing_date="2026-09-01",
                             transport=lambda url:(calls.append(url),wire())[1])
        self.assertEqual(len(calls),1)
        self.assertEqual(result["network_requests"],1)
        self.assertEqual(result["paired_engine_a"]["status"],"BLOCKED")
        self.assertIsNone(result["paired_engine_a"]["market_analysis"])

    def test_cli_invalid_stock_blocks_before_tty_or_fred_get(self):
        printed=[]
        with patch.object(cli,"_safe_date",return_value=AS_OF), (
            patch.object(api,"_get",side_effect=AssertionError("NO GET"))), (
            patch("builtins.print",side_effect=lambda *a,**k:printed.append(
                " ".join(map(str,a))))):
            code=cli.main(["--live","--stock-csv","/missing_file",
                           "--ticker","AAPL","--issuer-cik","0000320193",
                           "--filing-date","2026-07-31",
                           "--stock-source-url","https://example.org/source"])
        self.assertEqual(code,2)
        self.assertEqual(json.loads(printed[-1])["reason_code"],"LOCAL_STOCK_CSV_INVALID")

    def test_cli_one_get_local_pair_no_raw_or_path_leak(self):
        import tempfile
        from pathlib import Path
        from tests.test_fred_nasdaq100_offline import stock_data
        printed=[]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"stock.csv";path.write_bytes(stock_data())
            with patch.object(cli,"_safe_date",return_value=AS_OF),(
                patch.object(cli.sys.stdin,"isatty",return_value=True)),(
                patch.object(cli.sys.stdout,"isatty",return_value=True)),(
                patch("builtins.input",return_value=cli._APPROVAL)),(
                patch.object(cli.getpass,"getpass",return_value=KEY)),(
                patch.object(api,"_get",return_value=wire()) as get),(
                patch("builtins.print",side_effect=lambda *a,**k:printed.append(
                    " ".join(map(str,a))))):
                code=cli.main(["--live","--stock-csv",str(path),
                               "--ticker","AAPL","--issuer-cik","0000320193",
                               "--filing-date","2026-07-31",
                               "--stock-source-url","https://example.org/source"])
            self.assertEqual(code,0)
            get.assert_called_once()
            self.assertEqual(json.loads(printed[-1])["paired_engine_a"]
                             ["matched_observation_count"],42)
            self.assertNotIn(str(path),str(printed))
            self.assertNotIn(KEY,str(printed))
