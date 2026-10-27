"""SEC structured facts; exclusively offline tests, zero remote calls."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from proofinvest.sec_companyfacts import run_curated_apple_demo, verify_sec_annual_revenue

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/sec_apple_fy2025_curated_companyfacts.json"
KW = dict(cik="0000320193", accession="0000320193-25-000079",
          current_end="2025-09-27", prior_end="2024-09-28", as_of="2025-11-01")


class SecCompanyfactsTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(FIXTURE.read_text(encoding="utf8"))

    def run_verifier(self, **overrides):
        return verify_sec_annual_revenue(self.record, **(KW | overrides))

    def rows(self):
        return self.record["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]

    def test_calculates_apple_real_public_numbers_without_authenticating_source(self):
        result = self.run_verifier()
        self.assertEqual(result["growth_pct"], "6.43")
        self.assertEqual(result["current_usd"], "416161000000")
        self.assertEqual(result["prior_usd"], "391035000000")
        self.assertEqual(result["status"], "calculated_unverified")
        for flag in ("live_api_called", "authenticated_external_source", "ai_agent_executed",
                     "source_rights_verified", "risk_calculated", "official_contest_submission"):
            self.assertIs(result[flag], False)
        self.assertEqual(result["sec_filing_index"],
                         "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/0000320193-25-000079-index.htm")

    def test_future_filing_must_not_leak_back_into_past(self):
        v = self.run_verifier(as_of="2025-10-30")
        self.assertEqual(v["reason_code"], "FILING_AFTER_AS_OF")
        self.assertIsNone(v["growth_pct"])

    def test_issuer_mismatch(self):
        self.record["cik"] = 123456
        self.assertEqual(self.run_verifier()["reason_code"], "CIK_MISMATCH")

    def test_wrong_accession_cannot_mix_filings(self):
        self.assertEqual(self.run_verifier(accession="0000320193-24-000100")["reason_code"],
                         "ANNUAL_FACTS_UNAVAILABLE")

    def test_mixed_quarterly_and_short_annual_period_fails_closed(self):
        self.rows()[0]["start"] = "2025-07-01"
        self.assertEqual(self.run_verifier()["reason_code"], "INVALID_ANNUAL_PERIOD_OR_FILING_DATE")
        self.rows()[0]["form"] = "10-Q"
        self.assertEqual(self.run_verifier()["reason_code"], "ANNUAL_FACTS_UNAVAILABLE")

    def test_duplicate_identical_ok_but_conflicting_amounts_blocked(self):
        self.rows().append(copy.deepcopy(self.rows()[0]))
        self.assertEqual(self.run_verifier()["growth_pct"], "6.43")
        self.rows()[-1]["val"] += 1
        self.assertEqual(self.run_verifier()["reason_code"], "AMBIGUOUS_ANNUAL_FACTS")

    def test_mixed_units_and_negative_revenue_rejected(self):
        units = self.record["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]
        units["EUR"] = copy.deepcopy(units["USD"])
        self.assertEqual(self.run_verifier()["reason_code"], "UNSUPPORTED_OR_MIXED_UNITS")
        del units["EUR"]
        self.rows()[0]["val"] = -5
        self.assertEqual(self.run_verifier()["reason_code"], "INVALID_USD_REVENUE")

    def test_growth_claim_conflict_vs_matching_claim(self):
        self.assertEqual(self.run_verifier(claimed_growth_pct="30")["status"], "conflict")
        self.assertEqual(self.run_verifier(claimed_growth_pct="6.43")["status"], "calculated_unverified")
        self.assertEqual(self.run_verifier(claimed_growth_pct="NaN")["reason_code"], "INVALID_GROWTH_CLAIM")

    def test_zero_prior_and_invalid_date(self):
        self.rows()[1]["val"] = 0
        self.assertEqual(self.run_verifier()["reason_code"], "ZERO_PRIOR_REVENUE")
        self.assertEqual(self.run_verifier(as_of="2025-02-31")["reason_code"], "INVALID_INPUT")

    def test_filing_chronology(self):
        self.rows()[0]["filed"] = "2025-01-01"
        self.assertEqual(self.run_verifier()["reason_code"], "INVALID_FILING_CHRONOLOGY")

    def test_row_bound(self):
        rows = self.rows()
        rows *= 5001
        self.assertEqual(self.run_verifier()["reason_code"], "MISSING_OR_OVERSIZED_REVENUE_RECORDS")

    def test_curated_demo_labels_manual_excerpt(self):
        v = run_curated_apple_demo()
        self.assertEqual(v["growth_pct"], "6.43")
        self.assertIn("HUMAN_CURATED", v["demonstration_source"])
        self.assertEqual(run_curated_apple_demo(as_of="2025-10-30")["status"], "unavailable")

    def test_missing_curated_fixture_fails_closed(self):
        with patch.object(Path, "stat", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                run_curated_apple_demo()


if __name__ == "__main__":
    unittest.main()
