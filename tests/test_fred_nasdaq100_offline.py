"""P250 FRED true NASDAQ100 offline import, fail-closed rights and Engine A."""
from __future__ import annotations

from datetime import date, timedelta
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from proofinvest.fred_nasdaq100_offline import (
    parse_fred_nasdaq100_csv, parse_owner_stock_csv,
    analyze_offline_fred_pair,
)
from scripts import p250_fred_offline_check as cli

AS_OF = "2026-10-01"
FILING = "2026-07-31"
CIK = "0000320193"
SOURCE = "https://example.org/market-data"


def trading_days(n=65):
    start = date(2026, 7, 1)
    days = []
    for k in range(200):
        dt = start + timedelta(days=k)
        if dt.weekday() < 5:
            days.append(dt.isoformat())
        if len(days) == n:
            break
    return days


def fred_data(*, missing=None, date_header="observation_date", count=65):
    rows = [f"{date_header},NASDAQ100"]
    for i,d in enumerate(trading_days(count)):
        if missing is not None and i == missing:
            rows.append(f"{d},.")
        else:
            rows.append(f"{d},{10000+i*3.75:.3f}")
    return ("\n".join(rows) + "\n").encode()


def stock_data(*, omit=None, count=65):
    rows = ["date,close"]
    for i,d in enumerate(trading_days(count)):
        if omit and omit(i):
            continue
        rows.append(f"{d},{100+i*0.37 + i*i*0.004:.4f}")
    return ("\n".join(rows) + "\n").encode()


def receipts():
    return (
        parse_owner_stock_csv(stock_data(), ticker="AAPL", as_of=AS_OF,
                              source_url=SOURCE),
        parse_fred_nasdaq100_csv(fred_data(), as_of=AS_OF),
    )


class FredOfflineContractTests(unittest.TestCase):
    def test_real_series_identity_and_copy_rights_never_promoted(self):
        x = parse_fred_nasdaq100_csv(fred_data(),as_of=AS_OF)
        self.assertEqual(x["series_id"],"NASDAQ100")
        self.assertEqual(x["index_symbol"],"I:NDX")
        self.assertEqual(x["point_count"],65)
        self.assertEqual(x["first_date"],"2026-07-01")
        self.assertEqual(x["last_date"],"2026-09-29")
        self.assertFalse(x["source_authenticated"])
        self.assertFalse(x["source_rights_verified"])
        self.assertFalse(x["commercial_reuse_allowed"])
        self.assertFalse(x["public_display_allowed"])
        self.assertFalse(x["ai_processing_allowed"])
        self.assertEqual(len(x["source_sha256"]),64)

    def test_legacy_date_header_is_allowed_but_other_index_is_not(self):
        x=parse_fred_nasdaq100_csv(fred_data(date_header="DATE"),as_of=AS_OF)
        self.assertEqual(x["point_count"],65)
        with self.assertRaisesRegex(ValueError,"UNEXPECTED_CSV_SERIES_HEADER"):
            parse_fred_nasdaq100_csv(
                fred_data().replace(b"NASDAQ100",b"QQQ",1), as_of=AS_OF)

    def test_fred_missing_holiday_does_not_forward_fill(self):
        raw=fred_data(missing=8)
        result=parse_fred_nasdaq100_csv(raw,as_of=AS_OF)
        self.assertEqual(result["point_count"],64)
        self.assertEqual(result["missing_rows_ignored"],1)
        self.assertFalse(any(p["date"]==trading_days()[8]
                             for p in result["close_observations"]))

    def test_fred_weekend_price_rejected_not_reassigned(self):
        raw=fred_data().replace(
            b"2026-07-03,",b"2026-07-04,",1)
        with self.assertRaisesRegex(ValueError,"WEEKEND_DAILY_PRICE"):
            parse_fred_nasdaq100_csv(raw,as_of=AS_OF)


    def test_missing_fred_calendar_rows_must_still_obey_trading_date_and_asof(self):
        """A '.' price is not an exemption from calendar/source-vintage checks."""
        baseline = fred_data()
        # Replace the 2026-07-03 close row with an out-of-calendar missing row.
        for row, error in ((b"2026-07-04,.", "WEEKEND_DAILY_PRICE"),
                           (b"2026-10-02,.", "POST_AS_OF_DAILY_PRICE")):
            altered = baseline.replace(b"2026-07-03,10007.500", row, 1)
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, error):
                parse_fred_nasdaq100_csv(altered, as_of=AS_OF)
        # Ordinary missing market-holiday-style weekday rows remain allowed.
        valid = baseline.replace(b"2026-07-03,10007.500", b"2026-07-03,.", 1)
        parsed = parse_fred_nasdaq100_csv(valid, as_of=AS_OF)
        self.assertEqual(parsed["missing_rows_ignored"], 1)
        self.assertEqual(parsed["point_count"], 64)

    def test_duplicate_date_and_inversion_rejected(self):
        raw=fred_data().replace(
            b"2026-07-02,",b"2026-07-01,",1)
        with self.assertRaisesRegex(ValueError,"UNSORTED_DUPLICATE_CSV_DATE"):
            parse_fred_nasdaq100_csv(raw,as_of=AS_OF)
        raw=fred_data().replace(
            b"2026-07-03,",b"2026-07-01,",1)
        with self.assertRaisesRegex(ValueError,"UNSORTED_DUPLICATE_CSV_DATE"):
            parse_fred_nasdaq100_csv(raw,as_of=AS_OF)

    def test_unexpected_columns_bad_encoding_and_excel_formula_rejected(self):
        for raw in (b"observation_date,NASDAQ100,QQQ\n2026-07-01,1,2\n",
                    b"\x00"*50, b"\xff\xfe"*40):
            with self.subTest(raw=raw[:15]), self.assertRaises(ValueError):
                parse_fred_nasdaq100_csv(raw,as_of=AS_OF)
        raw=fred_data().replace(b"10000.000",b"=1+2",1)
        with self.assertRaisesRegex(ValueError,"INVALID_DAILY_CLOSE"):
            parse_fred_nasdaq100_csv(raw,as_of=AS_OF)

    def test_scientific_notation_negative_zero_and_nonfinite_block(self):
        for val in ("1e5","NaN","Inf","-7","0","12.345678999"):
            with self.subTest(val=val), self.assertRaisesRegex(
                    ValueError,"INVALID_DAILY_CLOSE"):
                raw=fred_data().replace(b"10000.000",val.encode(),1)
                parse_fred_nasdaq100_csv(raw,as_of=AS_OF)

    def test_after_asof_stale_and_future_asof_fail_closed(self):
        for asof in ("2026-09-01","2026-09-20","2099-01-01"):
            with self.subTest(asof=asof), self.assertRaises(ValueError):
                parse_fred_nasdaq100_csv(fred_data(),as_of=asof)
        with self.assertRaisesRegex(ValueError,"STALE_DAILY_OBSERVATIONS"):
            parse_fred_nasdaq100_csv(
                fred_data(count=45),as_of=AS_OF)

    def test_owner_stock_requires_https_and_not_index_proxy(self):
        with self.assertRaisesRegex(ValueError,"INVALID_STOCK_IDENTITY"):
            parse_owner_stock_csv(
                stock_data(),ticker="I:NDX",as_of=AS_OF,source_url=SOURCE)
        for source in ("http://example.com/stocks","https://evil.example/a?token=abc",
                       "https://localhost/stocks","https://user:pass@example.com"):
            with self.subTest(source=source),self.assertRaisesRegex(
                    ValueError,"INVALID_STOCK_IDENTITY"):
                parse_owner_stock_csv(stock_data(),ticker="AAPL",
                                      as_of=AS_OF,source_url=source)

    def test_actual_decimal_engine_a_with_local_stock_and_fred_csv(self):
        stock,ndx=receipts()
        outcome=analyze_offline_fred_pair(
            stock=stock,index=ndx,ticker="AAPL",issuer_cik=CIK,
            filing_date=FILING,as_of=AS_OF)
        self.assertEqual(outcome["status"],
                         "OFFLINE_FRED_ENGINE_A_DESCRIPTIVE_UNVERIFIED",outcome)
        self.assertEqual(outcome["matched_observation_count"],42)
        self.assertEqual(outcome["matched_period_start"],"2026-08-03")
        self.assertEqual(outcome["matched_period_end"],"2026-09-29")
        self.assertIsNotNone(outcome["market_analysis"]["beta"])
        self.assertEqual(outcome["network_requests"],0)
        self.assertFalse(outcome["source_authenticated"])
        self.assertFalse(outcome["source_rights_verified"])
        self.assertFalse(outcome["full_a_b_c_ready"])
        self.assertFalse(outcome["trade_executed"])

    def test_post_filing_31day_minimum_and_80pct_overlap_enforced(self):
        stock,ndx=receipts()
        for filing in ("2026-08-19","2026-09-01"):
            with self.subTest(filing=filing):
                out=analyze_offline_fred_pair(
                    stock=stock,index=ndx,ticker="AAPL",issuer_cik=CIK,
                    filing_date=filing,as_of=AS_OF)
                self.assertEqual(out["status"],"BLOCKED")
        sparse=parse_owner_stock_csv(stock_data(omit=lambda i:i%4==0),
                                     ticker="AAPL",as_of=AS_OF,source_url=SOURCE)
        out=analyze_offline_fred_pair(
            stock=sparse,index=ndx,ticker="AAPL",issuer_cik=CIK,
            filing_date=FILING,as_of=AS_OF)
        self.assertEqual(out["status"],"BLOCKED")

    def test_forged_source_rights_or_wrong_ticker_never_promoted(self):
        for field,value in (("source_authenticated",True),
                            ("source_rights_verified",True),
                            ("commercial_reuse_allowed",True),
                            ("ai_processing_allowed",True),
                            ("series_id","QQQ"),
                            ("source_sha256","deadbeef")):
            stock,ndx=receipts()
            ndx[field]=value
            with self.subTest(field=field):
                out=analyze_offline_fred_pair(
                    stock=stock,index=ndx,ticker="AAPL",issuer_cik=CIK,
                    filing_date=FILING,as_of=AS_OF)
                self.assertEqual(out["status"],"BLOCKED")
        stock,ndx=receipts()
        out=analyze_offline_fred_pair(
            stock=stock,index=ndx,ticker="MSFT",issuer_cik=CIK,
            filing_date=FILING,as_of=AS_OF)
        self.assertEqual(out["status"],"BLOCKED")

    def test_no_accidental_network_dependency(self):
        with patch("urllib.request.urlopen",side_effect=AssertionError("NO HTTP")):
            stock,idx=receipts()
            out=analyze_offline_fred_pair(
                stock=stock,index=idx,ticker="AAPL",issuer_cik=CIK,
                filing_date=FILING,as_of=AS_OF)
            self.assertEqual(out["network_requests"],0)

    def test_cli_safe_fred_only_no_network_and_no_input_paths(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"NAS100.csv"
            file.write_bytes(fred_data())
            lines=[]
            with patch("builtins.print",side_effect=lambda *x,**kw:
                       lines.append(" ".join(str(v) for v in x))):
                rc=cli.main(["--fred-csv",str(file),"--as-of",AS_OF])
            out=json.loads(lines[-1])
            self.assertEqual(rc,0)
            self.assertEqual(out["status"],"LOCAL_FRED_CSV_PARSED_ORIGIN_UNVERIFIED")
            self.assertEqual(out["points"],65)
            self.assertEqual(out["network_requests"],0)
            self.assertNotIn(str(file),json.dumps(out))
            self.assertFalse(out["market_data_rights_verified"])

    def test_cli_joins_stock_and_fred_locally(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"nas100.csv"; f.write_bytes(fred_data())
            p=Path(d)/"aapl.csv"; p.write_bytes(stock_data())
            lines=[]
            with patch("builtins.print",side_effect=lambda *x,**kw:
                       lines.append(" ".join(str(v) for v in x))):
                rc=cli.main(["--fred-csv",str(f),"--stock-csv",str(p),
                    "--ticker","AAPL","--issuer-cik",CIK,
                    "--filing-date",FILING,"--stock-source-url",SOURCE,
                    "--as-of",AS_OF])
            out=json.loads(lines[-1])
            self.assertEqual(rc,0,out)
            self.assertEqual(out["pair"]["status"],
                             "OFFLINE_FRED_ENGINE_A_DESCRIPTIVE_UNVERIFIED")
            self.assertFalse(out["pair"]["commercial_reuse_allowed"])
            self.assertNotIn(str(p),json.dumps(out))

    def test_cli_missing_file_never_discloses_path(self):
        lines=[]
        name="/THIS_IS_NOT_AN_EXISTING_SECRETS_DIRECTORY/NAS100.csv"
        with patch("builtins.print",side_effect=lambda *x,**kw:
                   lines.append(" ".join(str(v) for v in x))):
            rc=cli.main(["--fred-csv",name,"--as-of",AS_OF])
        out=json.loads(lines[-1])
        self.assertEqual(rc,2)
        self.assertEqual(out["network_requests"],0)
        self.assertNotIn(name,json.dumps(out))


if __name__=="__main__":
    unittest.main()
