"""P55 real public figure regression: inputs are manually transcribed, no API."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from proofinvest.public_primary_baseline import (
    APPLE, CURATED, SAMSUNG, _read, analyze_apple_manual_pair,
    run_public_primary_baseline,
)


class PublicPrimaryBaselineTests(unittest.TestCase):
    def setUp(self):
        self.apple = _read(APPLE)
        self.curated = _read(CURATED)
        self.samsung = _read(SAMSUNG)

    def test_actual_issuer_figures_match_existing_curated_facts(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_NETWORK")) as http:
            report = analyze_apple_manual_pair(self.apple, self.curated)
        http.assert_not_called()
        self.assertEqual(report["sales_growth_pct"], "6.43")
        self.assertEqual(report["accounts_receivable_growth_pct"], "19.06")
        self.assertEqual(report["accounts_receivable_minus_sales_growth_pp"], "12.63")
        self.assertEqual(report["operating_cashflow_growth_pct"], "-5.73")
        self.assertEqual(report["cash_to_net_income_pct"], "99.53")
        self.assertEqual(report["exploratory_review_signal"],
                         "REVIEW_RECEIVABLE_GROWTH_GAP_GT_10PP")
        self.assertFalse(report["raw_sec_companyfacts_authenticated"])
        self.assertFalse(report["fraud_proven"])

    def test_two_real_issuers_replayed_without_cross_currency_ranking(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_NETWORK")) as http:
            report = run_public_primary_baseline(self.apple, self.curated, self.samsung)
        http.assert_not_called()
        self.assertEqual(report["samsung"]["reported_growth_pct"], "16.20")
        self.assertIsNone(report["cross_issuer_absolute_comparison"])
        self.assertIsNone(report["cross_issuer_growth_ranking"])
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(report["real_world_a_b_c_end_to_end_verified"])

    def test_publisher_values_cannot_override_revenue_components(self):
        bad = copy.deepcopy(self.apple)
        bad["current"]["services_sales"] = "109159"
        with self.assertRaisesRegex(ValueError, "PUBLIC_SALES_COMPONENTS_CONFLICT"):
            analyze_apple_manual_pair(bad, self.curated)

    def test_gross_margin_reconciles_before_any_growth(self):
        bad = copy.deepcopy(self.apple)
        bad["prior"]["gross_margin"] = "180684"
        with self.assertRaisesRegex(ValueError, "PUBLIC_GROSS_MARGIN_CONFLICT"):
            analyze_apple_manual_pair(bad, self.curated)

    def test_public_pdf_and_sec_curated_revenue_mismatch_block(self):
        bad = copy.deepcopy(self.curated)
        bad["facts"]["us-gaap"][
            "RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"][0]["val"] += 1000000
        with self.assertRaisesRegex(ValueError, "PUBLIC_ISSUER_PDF_VS_CURATED_SEC_REVENUE_CONFLICT"):
            analyze_apple_manual_pair(self.apple, bad)

    def test_issuer_cik_accession_or_fiscal_period_tampering_block(self):
        for change in ("cik", "accession", "fiscal", "filed", "asof", "unit"):
            bad = copy.deepcopy(self.apple)
            if change == "cik": bad["cik"] = "0000000001"
            elif change == "accession": bad["filing_context"]["accession"] = "0000000000-00-000001"
            elif change == "fiscal": bad["current"]["end"] = "2025-09-28"
            elif change == "filed": bad["filing_context"]["filed_at"] = "2025-10-30"
            elif change == "asof": bad["as_of"] = "2025-10-30"
            elif change == "unit": bad["unit"] = "KRW_MILLIONS"
            with self.subTest(change=change), self.assertRaises(ValueError):
                analyze_apple_manual_pair(bad, self.curated)

    def test_source_origin_rights_and_publication_unauthenticated(self):
        for change in ("url", "date", "audit", "rights", "document"):
            bad = copy.deepcopy(self.apple)
            if change == "url": bad["source"]["url"] = "https://example.org/fake.pdf"
            elif change == "date": bad["source"]["release_date"] = "2026-10-30"
            elif change == "audit": bad["source"]["pdf_original_sha256_authenticated"] = True
            elif change == "rights": bad["source"]["distribution_rights_verified"] = True
            elif change == "document": bad["statement_status"] = "AUDITED_RAW_SEC_API"
            with self.subTest(change=change), self.assertRaises(ValueError):
                analyze_apple_manual_pair(bad, self.curated)

    def test_no_forged_duplicate_or_float_in_curated_values(self):
        for change in ("duplicate", "float", "wrong_date", "wrong_tag"):
            bad = copy.deepcopy(self.curated)
            rows = bad["facts"]["us-gaap"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
            if change == "duplicate": rows[1] = copy.deepcopy(rows[0])
            elif change == "float": rows[0]["val"] = float(rows[0]["val"])
            elif change == "wrong_date": rows[0]["start"] = "2024-09-30"
            elif change == "wrong_tag": rows[0]["form"] = "10-Q"
            with self.subTest(change=change), self.assertRaises(ValueError):
                analyze_apple_manual_pair(self.apple, bad)

    def test_malformed_metadata_or_numeric_input_rejected(self):
        for val in (True, 1.5, "1e6", "-1", "00010", "NaN", "9999999999999"):
            bad = copy.deepcopy(self.apple)
            bad["current"]["operating_income"] = val
            with self.subTest(value=val), self.assertRaises(ValueError):
                analyze_apple_manual_pair(bad, self.curated)

    def test_missing_samsung_original_receipt_blocks_aggregate(self):
        bad = copy.deepcopy(self.samsung)
        bad["unit"] = "USD_MILLIONS"
        with self.assertRaisesRegex(ValueError, "SAMSUNG_MANUAL_PUBLIC_RECEIPT_NOT_REPRODUCED"):
            run_public_primary_baseline(self.apple, self.curated, bad)

    def test_no_raw_pdf_committed_or_api_usage(self):
        report = run_public_primary_baseline(self.apple, self.curated, self.samsung)
        self.assertEqual(report["apple"]["sec_live_requests"], 0)
        self.assertFalse(report["live_api_called"])
        self.assertFalse(report["trade_executed"])
        self.assertFalse(report["ai_generated"])
        self.assertFalse(report["guard_policy_modified"])
        self.assertEqual(report["apple"]["statement_status"], "UNAUDITED_ISSUER_PRESS_RELEASE")


if __name__ == "__main__":
    unittest.main()
