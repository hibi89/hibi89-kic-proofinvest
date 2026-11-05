"""P258 owner-local Alpha Vantage JSON -> genuine FRED NASDAQ100 pairing.
Strictly offline fixtures; vendor rights and authenticated origin not granted.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from proofinvest.fred_nasdaq100_offline import (
    parse_owner_alpha_vantage_json, parse_fred_nasdaq100_csv,
    analyze_offline_fred_pair, plan_local_stock_for_fred_index,
)
from proofinvest import market_provider_fred_api as fred_api
from scripts import p252_fred_ndx_api_probe as cli
from tests.test_market_provider_alpha_vantage import fixture
from tests.test_fred_nasdaq100_offline import AS_OF, FILING, CIK, fred_data


class LocalAlphaToFredTests(unittest.TestCase):
    def setUp(self):
        self.original = fixture(symbol="AAPL")
        self.stock = parse_owner_alpha_vantage_json(
            self.original, ticker="AAPL", as_of=AS_OF)

    def test_digest_is_of_original_json_not_intermediate_csv(self):
        self.assertEqual(self.stock["source_sha256"],
                         sha256(self.original).hexdigest())
        self.assertEqual(self.stock["source_format"],"ALPHA_VANTAGE_OWNER_JSON")
        self.assertEqual(self.stock["provider"],"ALPHA_VANTAGE_OWNER_JSON_UNVERIFIED")
        self.assertEqual(self.stock["point_count"],65)
        for f in ("source_authenticated","source_rights_verified",
                  "commercial_reuse_allowed","ai_processing_allowed"):
            self.assertIs(self.stock[f],False)

    def test_json_stock_fred_index_engine_a(self):
        result=analyze_offline_fred_pair(
            stock=self.stock,
            index=parse_fred_nasdaq100_csv(fred_data(),as_of=AS_OF),
            ticker="AAPL",issuer_cik=CIK,filing_date=FILING,as_of=AS_OF)
        self.assertEqual(result["status"],
                         "OFFLINE_FRED_ENGINE_A_DESCRIPTIVE_UNVERIFIED",result)
        self.assertEqual(result["matched_observation_count"],42)
        self.assertEqual(result["stock_source_format"],"ALPHA_VANTAGE_OWNER_JSON")
        self.assertEqual(result["index_source_format"],"OWNER_CSV_UNVERIFIED")
        self.assertIsNotNone(result["market_analysis"]["beta"])
        self.assertIs(result["full_a_b_c_ready"],False)

    def test_local_preflight_uses_json_without_get(self):
        p=plan_local_stock_for_fred_index(
            stock=self.stock,ticker="AAPL",issuer_cik=CIK,
            filing_date=FILING,as_of=AS_OF)
        self.assertEqual(p["status"],"LOCAL_STOCK_READY_INDEX_REQUIRED_UNVERIFIED")
        self.assertEqual(p["eligible_post_filing_sessions"],42)
        self.assertEqual(p["network_requests"],0)

    def test_wrong_ticker_and_forged_provenance_fail(self):
        with self.assertRaises(ValueError):
            parse_owner_alpha_vantage_json(
                self.original,ticker="MSFT",as_of=AS_OF)
        for changed in ({"provider":"OWNER_CSV_ORIGIN_UNVERIFIED"},
                        {"source_authenticated":True},
                        {"commercial_reuse_allowed":True},
                        {"source_format":"OWNER_CSV_UNVERIFIED"}):
            s={**self.stock,**changed}
            p=plan_local_stock_for_fred_index(
                stock=s,ticker="AAPL",issuer_cik=CIK,
                filing_date=FILING,as_of=AS_OF)
            self.assertEqual(p["status"],"BLOCKED",changed)

    def test_cli_dry_run_json_has_no_network_no_private_rows(self):
        out=[]
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"owner-stock.json"
            file.write_bytes(self.original)
            with (patch.object(cli,"_safe_date",return_value=AS_OF),
                  patch.object(fred_api,"_get",
                               side_effect=AssertionError("NO_NETWORK")),
                  patch("builtins.print",
                        side_effect=lambda *xs,**kw:out.append(
                            " ".join(map(str,xs))))):
                code=cli.main(["--stock-alpha-json",str(file),
                               "--ticker","AAPL","--issuer-cik",CIK,
                               "--filing-date",FILING])
        self.assertEqual(code,0)
        r=json.loads(out[-1])
        self.assertEqual(r["status"],"DRY_RUN_PAIR_READY_NO_REQUEST")
        self.assertEqual(r["stock_preflight"]["eligible_post_filing_sessions"],42)
        self.assertNotIn(str(file),str(out))
        self.assertNotIn("close_observations",str(out))

    def test_cli_bad_json_and_spoofed_source_block_before_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"stock.json"
            file.write_bytes(fixture(symbol="MSFT"))
            for extra in ([],["--stock-source-url","https://evil.example/source"]):
                out=[]
                with (patch.object(cli,"_safe_date",return_value=AS_OF),
                      patch.object(fred_api,"_get",
                                   side_effect=AssertionError("NO_NETWORK")),
                      patch("builtins.print",
                            side_effect=lambda *xs,**kw:out.append(
                                " ".join(map(str,xs))))):
                    code=cli.main(["--stock-alpha-json",str(file),
                                   "--ticker","AAPL","--issuer-cik",CIK,
                                   "--filing-date",FILING]+extra)
                self.assertEqual(code,2)
                self.assertEqual(json.loads(out[-1])["reason_code"],
                                 "LOCAL_ALPHA_JSON_INVALID")


    def test_p250_paired_alpha_json_and_fred_csv_run_with_zero_network(self):
        from scripts import p250_fred_offline_check as offline
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as tmp:
            fred=Path(tmp)/"index.csv"
            stock=Path(tmp)/"stock.json"
            fred.write_bytes(fred_data())
            stock.write_bytes(self.original)
            output=io.StringIO()
            with (patch.object(fred_api, "_get",
                               side_effect=AssertionError("NO_FRED_GET")),
                  redirect_stdout(output)):
                rc=offline.main(["--fred-csv",str(fred),
                                 "--stock-alpha-json",str(stock),
                                 "--ticker","AAPL","--issuer-cik",CIK,
                                 "--filing-date",FILING,"--as-of",AS_OF])
            self.assertEqual(rc,0,output.getvalue())
            result=json.loads(output.getvalue())
            self.assertEqual(result["status"],
                             "LOCAL_FRED_CSV_PARSED_ORIGIN_UNVERIFIED")
            self.assertEqual(result["pair"]["matched_observation_count"],42)
            self.assertEqual(result["pair"]["stock_source_format"],
                             "ALPHA_VANTAGE_OWNER_JSON")
            self.assertEqual(result["network_requests"],0)
            self.assertFalse(result["market_data_rights_verified"])
            self.assertFalse(result["pair"]["full_a_b_c_ready"])
            self.assertNotIn(str(fred),output.getvalue())
            self.assertNotIn(str(stock),output.getvalue())
            self.assertNotIn("close_observations",output.getvalue())

    def test_p250_bad_alpha_json_rejected_without_raw_leak_or_http(self):
        from scripts import p250_fred_offline_check as offline
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as tmp:
            fred=Path(tmp)/"fred.csv"
            stock=Path(tmp)/"alpha.json"
            fred.write_bytes(fred_data())
            stock.write_bytes(fixture(symbol="MSFT"))
            out=io.StringIO()
            with redirect_stdout(out):
                rc=offline.main(["--fred-csv",str(fred),
                                 "--stock-alpha-json",str(stock),
                                 "--ticker","AAPL","--issuer-cik",CIK,
                                 "--filing-date",FILING,"--as-of",AS_OF])
            self.assertEqual(rc,2)
            result=json.loads(out.getvalue())
            self.assertEqual(result["status"],"BLOCKED")
            self.assertEqual(result["reason_code"],"FILE_OR_FORMAT_UNAVAILABLE")
            self.assertEqual(result["network_requests"],0)
            self.assertNotIn(str(stock),out.getvalue())

    def test_p250_alpha_json_with_owner_claimed_url_fails(self):
        from scripts import p250_fred_offline_check as offline
        import io
        from contextlib import redirect_stdout
        out=io.StringIO()
        with redirect_stdout(out):
            rc=offline.main(["--fred-csv","unopened.csv",
                             "--stock-alpha-json","unopened.json",
                             "--ticker","AAPL","--issuer-cik",CIK,
                             "--filing-date",FILING,"--as-of",AS_OF,
                             "--stock-source-url","https://wrong.example/"])
        self.assertEqual(rc,2)
        self.assertEqual(json.loads(out.getvalue())["reason_code"],
                         "STOCK_INPUT_INCOMPLETE")

    def test_direct_fred_call_still_requires_separate_approval(self):
        with patch.object(fred_api,"_get",
                          side_effect=AssertionError("NETWORK")):
            result=fred_api.run_one_fred_ndx_get(
                api_key="a"*32, as_of=AS_OF,
                paired_stock=self.stock, paired_ticker="AAPL",
                paired_issuer_cik=CIK,paired_filing_date=FILING)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["network_requests"],0)
        self.assertEqual(result["reason_code"],"FRED_APPROVAL_REQUIRED")
