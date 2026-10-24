"""Cross-entrypoint Risk regression: all input profiles here are synthetic.

engine.calculate is legacy and never upgrades input to authenticated Risk.
"""
import unittest

from proofinvest.engine import calculate
from proofinvest.risk import calculate_verified_debt_to_equity


def legacy_rows(debt="80", equity="30", ref="", currency="KRW"):
    return [
        {"account_nm": "부채총계", "fs_div": "CFS", "thstrm_amount": debt,
         "frmtrm_amount": "70", "rcept_no": ref, "currency": currency},
        {"account_nm": "자본총계", "fs_div": "CFS", "thstrm_amount": equity,
         "frmtrm_amount": "20", "rcept_no": ref, "currency": currency},
    ]


def gated_facts(debt="80", equity="30"):
    fields = {
        "state": "verified", "year": 2024, "fs_div": "CFS",
        "unit": "KRW", "report_code": "11011", "period_end": "2024-12-31",
        "issuer_id": "00126380", "evidence_ref": "SYNTHETIC_TEST_REPORT",
        "source_url": "https://example.org/synthetic-test-report",
        "source_kind": "SYNTHETIC_FIXTURE",
    }
    return [
        dict(fields, metric="liabilities", current_amount=debt),
        dict(fields, metric="equity", current_amount=equity),
    ]


class RiskEntrypointIntegrationTests(unittest.TestCase):
    def legacy_signal(self, debt="80", equity="30", ref="", demo=True, currency="KRW"):
        report = calculate(legacy_rows(debt, equity, ref, currency), 2024, is_demo=demo)
        return report["risk_signals"][0]

    def verified_signal(self, debt="80", equity="30"):
        return calculate_verified_debt_to_equity(
            gated_facts(debt, equity), expected_year=2024, demo=True,
        )

    def test_valid_synthetic_demo_agrees_on_ratio_and_threshold(self):
        legacy = self.legacy_signal()
        verified = self.verified_signal()
        self.assertEqual(legacy["value"], verified["ratio_pct"])
        self.assertEqual(legacy["triggered"], verified["triggered"])
        self.assertIsNone(legacy["withheld_reason_code"])
        self.assertFalse(verified["authenticated_external_source"])

    def test_negative_equity_never_becomes_false_safety_flag(self):
        legacy = self.legacy_signal(equity="-10")
        checked = self.verified_signal(equity="-10")
        self.assertEqual(legacy["withheld_reason_code"], "NEGATIVE_EQUITY")
        self.assertEqual(checked["withheld_reason_code"], "NEGATIVE_EQUITY")
        self.assertIsNone(legacy["value"])
        self.assertIsNone(legacy["triggered"])
        self.assertIsNone(checked["triggered"])

    def test_zero_equity_same_fail_closed_result(self):
        for value in ("0", "-0"):
            with self.subTest(value=value):
                legacy = self.legacy_signal(equity=value)
                checked = self.verified_signal(equity=value)
                self.assertEqual(legacy["withheld_reason_code"], "ZERO_EQUITY_DENOMINATOR")
                self.assertEqual(checked["withheld_reason_code"], "ZERO_EQUITY_DENOMINATOR")
                self.assertIsNone(legacy["value"])
                self.assertIsNone(legacy["triggered"])

    def test_negative_liabilities_does_not_calculate(self):
        legacy = self.legacy_signal(debt="-1")
        checked = self.verified_signal(debt="-1")
        self.assertEqual(legacy["withheld_reason_code"], "NEGATIVE_LIABILITIES")
        self.assertEqual(checked["withheld_reason_code"], "NEGATIVE_LIABILITIES")
        self.assertIsNone(legacy["triggered"])

    def test_missing_amount_in_legacy_does_not_trigger(self):
        for value in ("N/A", "", "-"):
            with self.subTest(value=value):
                signal = self.legacy_signal(equity=value)
                self.assertEqual(signal["withheld_reason_code"], "MISSING_FINANCIAL_AMOUNT")
                self.assertIsNone(signal["value"])
                self.assertIsNone(signal["triggered"])

    def test_nondemo_without_both_filing_refs_withheld(self):
        report = calculate(legacy_rows(ref=""), 2024, is_demo=False)
        signal = report["risk_signals"][0]
        self.assertEqual(signal["withheld_reason_code"], "UNVERIFIED_OR_CONFLICTING_FILING_REFERENCE")
        self.assertIsNone(signal["triggered"])
        self.assertEqual(report["status"], "financial_checks_only")

    def test_nondemo_mixed_filing_refs_withheld(self):
        rows = legacy_rows(ref="12345678901234")
        rows[1]["rcept_no"] = "99999999999999"
        result = calculate(rows, 2024, is_demo=False)["risk_signals"][0]
        self.assertEqual(result["withheld_reason_code"], "UNVERIFIED_OR_CONFLICTING_FILING_REFERENCE")
        self.assertIsNone(result["source"])
        self.assertIsNone(result["triggered"])

    def test_format_only_filing_ref_does_not_mean_authenticity(self):
        # The 14-digit string is syntactically plausible, NOT a real DART receipt.
        report = calculate(legacy_rows(ref="12345678901234"), 2024, is_demo=False)
        signal = report["risk_signals"][0]
        self.assertTrue(signal["triggered"])
        self.assertEqual(signal["value"], "266.67")
        self.assertIn("실 공시 인증 아님", signal["note"])
        self.assertEqual(report["status"], "financial_checks_only")

    def test_currency_mismatch_not_treated_as_valid_ratio(self):
        signal = self.legacy_signal(currency="USD")
        self.assertEqual(signal["withheld_reason_code"], "UNSUPPORTED_CURRENCY")
        self.assertIsNone(signal["triggered"])


if __name__ == "__main__":
    unittest.main()
