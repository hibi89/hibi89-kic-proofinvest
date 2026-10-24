"""Manual official-financial-statement evidence; no OpenDART/HTTP test calls."""
import json
import unittest
from decimal import Decimal
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent.parent / "docs" / "evidence" / "samsung_2024_cfs_revenue.json"


class PublicFilingEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_actual_official_pdf_and_statement_basis_recorded(self):
        data = self.evidence
        self.assertEqual(data["evidence_type"], "MANUAL_PRIMARY_SOURCE_VERIFICATION")
        self.assertEqual(data["financial_statement"], "CFS")
        self.assertEqual(data["unit"], "KRW_MILLIONS")
        self.assertEqual(data["report_year"], 2024)
        self.assertEqual(data["report_type"], "ANNUAL")
        self.assertTrue(data["primary_source"]["visual_verified"])
        self.assertTrue(data["primary_source"]["url"].startswith("https://images.samsung.com/"))

    def test_comparable_annual_periods(self):
        data = self.evidence
        self.assertEqual(data["current"]["period_start"], "2024-01-01")
        self.assertEqual(data["current"]["period_end"], "2024-12-31")
        self.assertEqual(data["previous"]["period_start"], "2023-01-01")
        self.assertEqual(data["previous"]["period_end"], "2023-12-31")

    def test_original_revenue_growth_recomputes_with_decimal(self):
        data = self.evidence
        current = Decimal(data["current"]["amount"])
        previous = Decimal(data["previous"]["amount"])
        self.assertEqual(current, Decimal("300870903"))
        self.assertEqual(previous, Decimal("258935494"))
        self.assertEqual(current - previous, Decimal(data["result"]["absolute_change"]))
        growth = ((current - previous) / previous * 100).quantize(Decimal("0.01"))
        self.assertEqual(growth, Decimal(data["result"]["growth_pct_rounded_2dp"]))
        self.assertEqual(growth, Decimal("16.20"))

    def test_dart_viewer_is_not_falsely_claimed_verified(self):
        dart = self.evidence["dart_filing"]
        self.assertFalse(dart["direct_viewer_verified"])
        self.assertRegex(dart["reference_only"], r"^\d{14}$")
        self.assertTrue(dart["url"].startswith("https://dart.fss.or.kr/"))


if __name__ == "__main__":
    unittest.main()
