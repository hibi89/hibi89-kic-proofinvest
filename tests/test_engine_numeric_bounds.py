"""Unrepresentable revenue growth must be withheld without crashing offline reports."""
import unittest

from proofinvest.engine import calculate


class ExcessiveMagnitudeGrowthTests(unittest.TestCase):
    @staticmethod
    def revenue_row(receipt=""):
        return [{
            "account_nm": "매출액",
            "fs_div": "CFS",
            "thstrm_amount": "9" * 80,
            "frmtrm_amount": "1",
            "rcept_no": receipt,
            "currency": "KRW",
        }]

    def test_large_synthetic_yoy_is_unavailable_not_crash(self):
        report = calculate(self.revenue_row(), 2024, "20", is_demo=True)
        self.assertEqual(report["status"], "demo_not_real")
        check = report["checks"][0]
        self.assertEqual(check["state"], "unavailable")
        self.assertIsNone(check["value"])
        self.assertIsNone(check["source"])
        self.assertIn("계산", check["explanation"])
        self.assertIsNone(report["risk_signals"][0]["triggered"])

    def test_large_non_synthetic_yoy_with_reference_still_withheld(self):
        # A well-formed receipt is NOT proof of authentic filing content.
        report = calculate(self.revenue_row("20250311001085"), 2024, "20")
        self.assertEqual(report["source_kind"], "OPENDART")
        check = report["checks"][0]
        self.assertEqual(check["state"], "unavailable")
        self.assertIsNone(check["value"])
        self.assertIsNone(check["source"])


if __name__ == "__main__":
    unittest.main()
