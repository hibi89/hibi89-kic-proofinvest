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
        "form": ["10-Q", "10-K", "10-K"],
        "accessionNumber": [
            "0001045810-25-000030", "0001045810-25-000020",
            "0001045810-24-000010"],
        "filingDate": [
            "2025-10-31", "2025-10-15", "2024-10-15"],
        "reportDate": [
            "2025-09-30", "2025-09-30", "2024-09-30"],
        "primaryDocument": ["q.htm", "annual2025.htm", "annual2024.htm"],
    }}}).encode()


def amended_submissions():
    """Explicit post-10-K amendment test case, not a baseline valid filing."""
    obj = json.loads(submissions())
    recent = obj["filings"]["recent"]
    recent["form"].append("10-K/A")
    recent["accessionNumber"].append("0001045810-25-000040")
    recent["filingDate"].append("2025-10-17")
    recent["reportDate"].append("2025-09-30")
    recent["primaryDocument"].append("amend.htm")
    return json.dumps(obj).encode()


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

    def test_same_fiscal_10k_amendment_prevents_stale_original_selection(self):
        # 2025-10-16 is before the 10-K/A; the initial filing remains valid.
        before = intake.build_ticker_source_plan(
            ticker="NVDA", ticker_map=mapping(),
            submissions=amended_submissions(), as_of="2025-10-16")
        self.assertEqual(before["status"], "10k_source_plan_unverified")
        self.assertEqual(before["latest_10k"]["accession"],
                         "0001045810-25-000020")
        # Once a same-fiscal-period amendment is visible, this four-source
        # pipeline must not silently review only the older 10-K.
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_EXTERNAL_SEC_GET")) as net:
            after = intake.build_ticker_source_plan(
                ticker="NVDA", ticker_map=mapping(),
                submissions=amended_submissions(), as_of="2025-10-17")
        net.assert_not_called()
        self.assertEqual(after["status"], "unavailable")
        self.assertEqual(after["reason_code"], "10K_AMENDMENT_REVIEW_REQUIRED")
        self.assertNotIn("latest_10k", after)
        self.assertFalse(after["source_authenticated"])
        self.assertFalse(after["full_a_b_c_ready"])
        self.assertEqual(after["network_requests"], 0)

    def test_older_fiscal_amendment_is_not_mistaken_for_latest_10k(self):
        data = json.loads(amended_submissions())
        data["filings"]["recent"]["reportDate"][3] = "2024-09-30"
        result = intake.build_ticker_source_plan(
            ticker="NVDA", ticker_map=mapping(),
            submissions=json.dumps(data).encode(), as_of="2025-10-17")
        self.assertEqual(result["status"], "10k_source_plan_unverified")
        self.assertEqual(result["latest_10k"]["accession"],
                         "0001045810-25-000020")

    def test_amendment_without_report_date_requires_manual_review(self):
        data = json.loads(amended_submissions())
        data["filings"]["recent"]["reportDate"][3] = ""
        result = intake.build_ticker_source_plan(
            ticker="NVDA", ticker_map=mapping(),
            submissions=json.dumps(data).encode(), as_of="2025-10-17")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason_code"], "10K_AMENDMENT_REVIEW_REQUIRED")

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


    def test_valid_agent_submitted_accession_uses_issuer_archive_directory(self):
        # Submitter != issuer: company submissions metadata, not the
        # accession's prefix, identifies the company whose filing is listed.
        obj = json.loads(submissions())
        obj["filings"]["recent"]["accessionNumber"][1] = "0000999999-25-000020"
        actual = intake.build_ticker_source_plan(
            ticker="NVDA", ticker_map=mapping(),
            submissions=json.dumps(obj).encode(), as_of="2025-10-16")
        self.assertEqual(actual["status"], "10k_source_plan_unverified")
        filing = actual["latest_10k"]
        self.assertEqual(filing["accession"], "0000999999-25-000020")
        self.assertEqual(filing["issuer_cik"], "0001045810")
        self.assertEqual(filing["accession_submitter_cik_from_identifier"], "0000999999")
        self.assertFalse(filing["accession_prefix_matches_issuer"])
        self.assertEqual(
            filing["original_filing_url"],
            "https://www.sec.gov/Archives/edgar/data/1045810/"
            "000099999925000020/annual2025.htm",
        )
        self.assertFalse(filing["original_authenticated"])



if __name__ == "__main__":
    import unittest
    unittest.main()
