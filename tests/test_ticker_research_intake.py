"""P98 synthetic-only ticker/10-K provenance and no-network regression."""
from __future__ import annotations

from contextlib import redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from proofinvest import ticker_research_intake as intake


def mapping():
    return json.dumps({
        "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "SYNTHETIC ISSUER"},
        "1": {"cik_str": 320193, "ticker": "AAPL", "title": "OTHER SYNTHETIC"}
    }).encode()


def submissions():
    return json.dumps({"cik": 1045810, "filings": {"recent": {
        "form": ["10-Q", "10-K", "10-K", "10-K/A"],
        "accessionNumber": [
            "0001045810-25-000030", "0001045810-25-000020",
            "0001045810-24-000010", "0001045810-25-000040"],
        "filingDate": [
            "2025-10-31", "2025-10-15", "2024-10-15", "2025-10-16"],
        "reportDate": [
            "2025-09-30", "2025-09-30", "2024-09-30", "2025-09-30"],
        "primaryDocument": ["q.htm", "annual2025.htm", "annual2024.htm", "amend.htm"],
    }}}).encode()


class SingleTickerIntakeTests(TestCase):
    def test_exact_symbol_resolves_pinned_cik_and_never_calls_http(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("UNAUTHORIZED_HTTP")) as opened:
            r = intake.build_ticker_source_plan(ticker=" nvda ", ticker_map=mapping())
        opened.assert_not_called()
        self.assertEqual(r["ticker"], "NVDA")
        self.assertEqual(r["cik"], "0001045810")
        self.assertEqual(r["ticker_map_sha256"], sha256(mapping()).hexdigest())
        self.assertEqual(r["sec_submissions_url"],
                         "https://data.sec.gov/submissions/CIK0001045810.json")
        self.assertFalse(r["source_authenticated"])
        self.assertFalse(r["full_a_b_c_ready"])
        self.assertEqual(r["network_requests"], 0)

    def test_single_10k_excludes_future_quarterly_and_amendment(self):
        r = intake.build_ticker_source_plan(ticker="NVDA", ticker_map=mapping(),
                                             submissions=submissions(), as_of="2025-10-16")
        self.assertEqual(r["status"], "10k_source_plan_unverified")
        self.assertEqual(r["latest_10k"]["accession"], "0001045810-25-000020")
        self.assertEqual(r["latest_10k"]["original_filing_url"],
                         "https://www.sec.gov/Archives/edgar/data/1045810/"
                         "000104581025000020/annual2025.htm")
        self.assertFalse(r["latest_10k"]["point_in_time_verified"])

    def test_historical_as_of_selects_prior_10k(self):
        r = intake.build_ticker_source_plan(ticker="NVDA", ticker_map=mapping(),
                                             submissions=submissions(), as_of="2024-12-01")
        self.assertEqual(r["latest_10k"]["accession"], "0001045810-24-000010")

    def test_invalid_input_ambiguous_symbol_fail_closed(self):
        for symbol in ("../NVDA", "NVIDIA", "NVDA\n", "BRK.B"):
            r = intake.build_ticker_source_plan(ticker=symbol, ticker_map=mapping())
            if symbol == "NVDA\n":
                # Whitespaces around a valid ticker are accepted.
                self.assertEqual(r["status"], "source_plan_only_unverified")
            else:
                self.assertEqual(r["status"], "unavailable")
        data = json.loads(mapping())
        data["2"] = {"ticker": "NVDA", "cik_str": 999, "title": "DUPLICATE"}
        self.assertEqual(intake.build_ticker_source_plan(
            ticker="NVDA", ticker_map=json.dumps(data).encode())["reason_code"],
            "TICKER_AMBIGUOUS")
        self.assertEqual(intake.build_ticker_source_plan(
            ticker="NVDA", ticker_map=b'{"0":{},"0":{}}')["reason_code"],
            "DUPLICATE_JSON_KEY")

    def test_unrelated_special_sec_symbol_does_not_block(self):
        data = json.loads(mapping())
        data["2"] = {"ticker": "SPECIAL^B", "cik_str": 999, "title": "OTHER"}
        r = intake.build_ticker_source_plan(ticker="NVDA",
                                             ticker_map=json.dumps(data).encode())
        self.assertEqual(r["cik"], "0001045810")

    def test_wrong_company_accession_path_and_columns_block(self):
        r = json.loads(submissions())
        r["cik"] = 999
        got = intake.build_ticker_source_plan(ticker="NVDA", ticker_map=mapping(),
                                             submissions=json.dumps(r).encode(),
                                             as_of="2025-10-16")
        self.assertEqual(got["reason_code"], "SUBMISSIONS_CIK_MISMATCH")
        self.assertNotIn("latest_10k", got)
        r = json.loads(submissions())
        r["filings"]["recent"]["primaryDocument"][1] = "../secret.htm"
        self.assertEqual(intake.build_ticker_source_plan(
            ticker="NVDA", ticker_map=mapping(), submissions=json.dumps(r).encode(),
            as_of="2025-10-16")["reason_code"], "UNSAFE_FILING_IDENTIFIER")
        r = json.loads(submissions())
        r["filings"]["recent"]["form"].pop()
        self.assertEqual(intake.build_ticker_source_plan(
            ticker="NVDA", ticker_map=mapping(), submissions=json.dumps(r).encode(),
            as_of="2025-10-16")["reason_code"], "SUBMISSIONS_ARRAY_LENGTH_MISMATCH")

    def test_no_as_of_or_no_eligible_10k(self):
        self.assertEqual(intake.build_ticker_source_plan(
            ticker="NVDA", ticker_map=mapping(), submissions=submissions())["reason_code"],
            "AS_OF_REQUIRED")
        self.assertEqual(intake.build_ticker_source_plan(
            ticker="NVDA", ticker_map=mapping(), submissions=submissions(),
            as_of="2020-01-01")["reason_code"], "NO_10K_BEFORE_AS_OF_IN_RECENT_WINDOW")

    def test_offline_cli_shows_no_owner_filename_or_http(self):
        with TemporaryDirectory() as base:
            folder = Path(base) / "private-docs"
            folder.mkdir()
            f = folder / "ticker_map.json"
            f.write_bytes(mapping())
            s = folder / "submissions.json"
            s.write_bytes(submissions())
            out = io.StringIO()
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("UNAUTHORIZED_HTTP")):
                with redirect_stdout(out):
                    status = intake.main(["--ticker", "NVDA", "--ticker-map", str(f),
                                          "--submissions", str(s),
                                          "--as-of", "2025-10-16"])
            self.assertEqual(status, 0)
            self.assertNotIn(str(folder), out.getvalue())
            self.assertEqual(json.loads(out.getvalue())["status"],
                             "10k_source_plan_unverified")


if __name__ == "__main__":
    import unittest
    unittest.main()
