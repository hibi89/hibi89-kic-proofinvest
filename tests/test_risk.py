"""Fail-closed Risk input gate, synthetic only; no API and no investment decision."""
import copy
import unittest

from proofinvest.risk import gate_verified_risk_inputs, calculate_verified_debt_to_equity
from proofinvest.evidence_scenarios import verify_growth_claim


def facts():
    common = {
        "state": "verified", "year": 2024, "fs_div": "CFS",
        "unit": "KRW", "report_code": "11011", "period_end": "2024-12-31",
        "issuer_id": "00126380", "evidence_ref": "SYNTHETIC_TEST_REPORT",
        "source_url": "https://example.org/synthetic-test-report",
        "source_kind": "SYNTHETIC_FIXTURE",
    }
    return [
        dict(common, metric="liabilities", current_amount="80"),
        dict(common, metric="equity", current_amount="30"),
    ]


def gate(data=None, **kw):
    return gate_verified_risk_inputs(facts() if data is None else data,
                                    expected_year=2024, demo=True, **kw)


class VerifiedOnlyRiskGateTests(unittest.TestCase):
    def test_synthetic_verified_matching_facts_eligible_without_risk_calculation(self):
        out = gate()
        self.assertEqual(out["status"], "eligible")
        self.assertEqual(out["facts"], {"liabilities": "80", "equity": "30"})
        self.assertFalse(out["authenticated_external_source"])
        self.assertFalse(out["risk_calculated"])
        self.assertTrue(out["is_demo"])

    def test_rejects_conflict_and_unavailable_even_with_numeric_values(self):
        for state in ("conflict", "unavailable", None):
            with self.subTest(state=state):
                data = facts()
                data[0]["state"] = state
                self.assertEqual(gate(data)["status"], "unavailable")
                self.assertEqual(gate(data)["facts"], {})

    def test_rejects_missing_duplicate_and_unrelated_metrics(self):
        data = facts()
        self.assertEqual(gate([])["status"], "unavailable")
        self.assertEqual(gate(data[:1])["status"], "unavailable")
        data[1]["metric"] = "liabilities"
        self.assertEqual(gate(data)["status"], "unavailable")
        data[1]["metric"] = "revenue_yoy_pct"
        self.assertEqual(gate(data)["status"], "unavailable")

    def test_growth_claim_verified_is_not_verified_balance_sheet_fact(self):
        growth_claim = {"metric": "revenue_yoy_pct", "state": "verified",
                        "computed_pct": "16.20"}
        self.assertEqual(gate([growth_claim, facts()[1]])["status"], "unavailable")
        self.assertEqual(verify_growth_claim(None, "16.20")["state"], "unavailable")

    def test_rejects_cross_statement_and_cross_year_mix(self):
        for field, value in (("year", 2023), ("fs_div", "OFS"),
                             ("report_code", "11013"), ("period_end", "2023-12-31")):
            with self.subTest(field=field):
                data = facts()
                data[1][field] = value
                self.assertEqual(gate(data)["status"], "unavailable")

    def test_rejects_different_issuer_source_report_or_provenance(self):
        for field, value in (("issuer_id", "00000001"), ("evidence_ref", "OTHER_REPORT"),
                             ("source_url", "https://example.org/another"),
                             ("source_kind", "MANUAL_PRIMARY_SOURCE_VERIFICATION")):
            with self.subTest(field=field):
                data = facts()
                data[1][field] = value
                self.assertEqual(gate(data)["status"], "unavailable")

    def test_rejects_invalid_currency_and_bad_numbers(self):
        for field, value in (("unit", "USD"), ("current_amount", "N/A"),
                             ("current_amount", "NaN"), ("current_amount", None)):
            with self.subTest(field=field, value=value):
                data = facts()
                data[1][field] = value
                self.assertEqual(gate(data)["status"], "unavailable")

    def test_rejects_invalid_http_and_missing_source(self):
        for url in ("http://example.org/report", "https://", "", None,
                    "https://user:pass@example.org/report"):
            with self.subTest(url=url):
                data = facts()
                data[0]["source_url"] = url
                self.assertEqual(gate(data)["status"], "unavailable")

    def test_rejects_unverified_synthetic_data_when_demo_is_false(self):
        self.assertEqual(
            gate_verified_risk_inputs(facts(), expected_year=2024)["status"],
            "unavailable",
        )
        self.assertEqual(
            gate_verified_risk_inputs(facts(), expected_year=2024, demo="yes")["status"],
            "unavailable",
        )

    def test_real_manual_provenance_remains_unauthed_although_eligible(self):
        data = facts()
        for x in data:
            x["source_kind"] = "MANUAL_PRIMARY_SOURCE_VERIFICATION"
        out = gate_verified_risk_inputs(data, expected_year=2024)
        self.assertEqual(out["status"], "eligible")
        self.assertFalse(out["authenticated_external_source"])
        self.assertFalse(out["risk_calculated"])

    def test_unhashable_source_kind_fails_closed_instead_of_crashing(self):
        data = facts()
        for malformed in ([], {}, ["SYNTHETIC_FIXTURE"]):
            with self.subTest(kind=malformed):
                data[0]["source_kind"] = malformed
                self.assertEqual(gate(data)["status"], "unavailable")

    def test_invalid_request_shape_fails_closed(self):
        self.assertEqual(gate_verified_risk_inputs(None, expected_year=2024)["status"], "unavailable")
        self.assertEqual(gate_verified_risk_inputs("verified", expected_year=2024)["status"], "unavailable")
        self.assertEqual(gate_verified_risk_inputs(facts(), expected_year=True, demo=True)["status"], "unavailable")
        self.assertEqual(gate_verified_risk_inputs(facts(), expected_year=2024, expected_statement="UNKNOWN", demo=True)["status"], "unavailable")

    def test_pure_and_order_invariant(self):
        values = facts()
        saved = copy.deepcopy(values)
        first = gate(values)
        self.assertEqual(first, gate(list(reversed(values))))
        self.assertEqual(values, saved)
        self.assertIsNone(first.get("ratio_pct"))




class VerifiedDebtToEquityCalculationTests(unittest.TestCase):
    def compute(self, data=None, **kwargs):
        return calculate_verified_debt_to_equity(
            facts() if data is None else data,
            expected_year=2024, demo=True, **kwargs,
        )

    def test_verified_data_calculates_and_triggers_exploratory_threshold(self):
        out = self.compute()
        self.assertEqual(out["status"], "calculated")
        self.assertEqual(out["ratio_pct"], "266.67")
        self.assertIsNone(out["withheld_reason_code"])
        self.assertTrue(out["triggered"])
        self.assertTrue(out["risk_calculated"])
        self.assertFalse(out["authenticated_external_source"])
        self.assertEqual(out["source_kind"], "SYNTHETIC_FIXTURE")
        self.assertEqual(out["threshold_pct"], 200)
        self.assertEqual(out["threshold_operator"], ">=")
        self.assertEqual(out["comparison_basis"], "unrounded_decimal_ratio")
        self.assertEqual(out["display_rounding"], "ROUND_HALF_UP_2DP")
        self.assertEqual(out["comparison_ratio_pct"], "266.6666666666666666666666667")
        self.assertIn("투자 판단 기준이 아님", out["note"])

    def test_valid_ratio_below_threshold(self):
        data = facts()
        data[0]["current_amount"] = "20"
        out = self.compute(data)
        self.assertEqual(out["ratio_pct"], "66.67")
        self.assertFalse(out["triggered"])

    def test_exact_threshold_triggers(self):
        data = facts()
        data[0]["current_amount"] = "60"
        result = self.compute(data)
        self.assertTrue(result["triggered"])
        self.assertEqual(result["comparison_ratio_pct"], "200")

    def test_unrounded_ratio_controls_trigger(self):
        data = facts()
        data[0]["current_amount"] = "59.999"
        out = self.compute(data)
        self.assertEqual(out["ratio_pct"], "200.00")
        self.assertEqual(out["comparison_ratio_pct"], "199.9966666666666666666666667")
        self.assertFalse(out["triggered"])
        self.assertIn("미반올림", out["note"])

    def test_threshold_metadata_consistent_across_calculated_and_withheld(self):
        good = self.compute()
        data = facts()
        data[1]["current_amount"] = "0"
        held = self.compute(data)
        for out in (good, held):
            self.assertEqual(out["threshold_pct"], 200)
            self.assertEqual(out["threshold_operator"], ">=")
            self.assertEqual(out["comparison_basis"], "unrounded_decimal_ratio")
            self.assertEqual(out["display_rounding"], "ROUND_HALF_UP_2DP")
            self.assertIn("투자 판단 기준이 아님", out["note"])
        self.assertEqual(held["status"], "unavailable")
        self.assertIsNone(held["comparison_ratio_pct"])
        self.assertIsNone(held["triggered"])

    def test_exploratory_rule_never_authenticates_external_source(self):
        data = facts()
        for fact in data:
            fact["source_kind"] = "MANUAL_PRIMARY_SOURCE_VERIFICATION"
        result = calculate_verified_debt_to_equity(data, expected_year=2024)
        self.assertEqual(result["status"], "calculated")
        self.assertTrue(result["triggered"])
        self.assertFalse(result["authenticated_external_source"])
        self.assertEqual(result["threshold_operator"], ">=")
        self.assertIn("시연용", result["note"])

    def test_zero_equity_safely_withheld(self):
        data = facts()
        data[1]["current_amount"] = "0"
        out = self.compute(data)
        self.assertEqual(out["status"], "unavailable")
        self.assertIsNone(out["ratio_pct"])
        self.assertIsNone(out["triggered"])
        self.assertEqual(out["withheld_reason_code"], "ZERO_EQUITY_DENOMINATOR")
        self.assertFalse(out["risk_calculated"])
        self.assertIn("Zero equity", out["reason"])

    def test_negative_equity_safely_withheld(self):
        data = facts()
        data[1]["current_amount"] = "-30"
        out = self.compute(data)
        self.assertEqual(out["status"], "unavailable")
        self.assertFalse(out["risk_calculated"])
        self.assertIsNone(out["triggered"])
        self.assertIn("Negative equity", out["reason"])
        self.assertEqual(out["withheld_reason_code"], "NEGATIVE_EQUITY")
        self.assertIn("위험 없음", out["withheld_explanation_ko"])
        self.assertIsNone(out["ratio_pct"])
        self.assertIsNone(out["comparison_ratio_pct"])

    def test_negative_equity_does_not_report_naive_negative_ratio_as_safe(self):
        data = facts()
        data[0]["current_amount"] = "80"
        data[1]["current_amount"] = "-10"
        # Naive signed 80 / -10 * 100 = -800%, misleadingly below 200%.
        out = self.compute(data)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["withheld_reason_code"], "NEGATIVE_EQUITY")
        self.assertIn("자본총계가 음수", out["withheld_explanation_ko"])
        self.assertIn("별도 공시 확인", out["withheld_explanation_ko"])
        self.assertIsNone(out["triggered"])
        self.assertIsNone(out["ratio_pct"])
        self.assertIsNone(out["comparison_ratio_pct"])
        self.assertFalse(out["risk_calculated"])
        self.assertFalse(out["authenticated_external_source"])
        self.assertEqual(out["facts"]["equity"], "-10")

    def test_negative_equity_with_zero_liabilities_still_withheld(self):
        data = facts()
        data[0]["current_amount"] = "0"
        data[1]["current_amount"] = "-1"
        result = self.compute(data)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["withheld_reason_code"], "NEGATIVE_EQUITY")
        self.assertIsNone(result["triggered"])
        self.assertIsNone(result["ratio_pct"])
        self.assertFalse(result["risk_calculated"])

    def test_withheld_explanation_only_for_negative_or_zero_equity(self):
        good = self.compute()
        self.assertIsNone(good["withheld_explanation_ko"])
        neg = facts()
        neg[1]["current_amount"] = "-0.01"
        neg_result = self.compute(neg)
        self.assertEqual(neg_result["withheld_reason_code"], "NEGATIVE_EQUITY")
        self.assertIsInstance(neg_result["withheld_explanation_ko"], str)
        zero = facts()
        zero[1]["current_amount"] = "0"
        zero_result = self.compute(zero)
        self.assertEqual(zero_result["withheld_reason_code"], "ZERO_EQUITY_DENOMINATOR")
        self.assertIn("정의되지", zero_result["withheld_explanation_ko"])
        absent = facts()
        absent[1]["current_amount"] = None
        absent_result = self.compute(absent)
        self.assertEqual(absent_result["withheld_reason_code"], "MISSING_FINANCIAL_AMOUNT")
        self.assertIsNone(absent_result["withheld_explanation_ko"])

    def test_missing_equity_never_bypasses_gate(self):
        for value in (None, "", "N/A"):
            with self.subTest(value=value):
                data = facts()
                data[1]["current_amount"] = value
                out = self.compute(data)
                self.assertEqual(out["status"], "unavailable")
                self.assertEqual(out["facts"], {})
                self.assertIsNone(out["ratio_pct"])

    def test_missing_amount_reports_structured_reason_without_risk(self):
        for metric_index in (0, 1):
            for raw in (None, "", "N/A", "-", "   "):
                with self.subTest(metric=metric_index, raw=raw):
                    data = facts()
                    data[metric_index]["current_amount"] = raw
                    out = self.compute(data)
                    self.assertEqual(out["status"], "unavailable")
                    self.assertEqual(out["withheld_reason_code"], "MISSING_FINANCIAL_AMOUNT")
                    self.assertIsNone(out["ratio_pct"])
                    self.assertIsNone(out["comparison_ratio_pct"])
                    self.assertIsNone(out["triggered"])
                    self.assertFalse(out["risk_calculated"])
                    self.assertEqual(out["facts"], {})

    def test_missing_fact_row_not_confused_with_zero_denominator(self):
        data = facts()
        for incomplete in ([], data[:1]):
            with self.subTest(rows=len(incomplete)):
                out = self.compute(incomplete)
                self.assertEqual(out["status"], "unavailable")
                self.assertEqual(out["withheld_reason_code"], "REQUIRED_FACTS_MISSING_OR_INVALID")
                self.assertIsNone(out["ratio_pct"])
                self.assertIsNone(out["triggered"])

    def test_malformed_numeric_values_fail_without_ratio(self):
        for raw in ("NaN", "not_a_number", "1e3"):
            with self.subTest(value=raw):
                data = facts()
                data[1]["current_amount"] = raw
                out = self.compute(data)
                self.assertEqual(out["status"], "unavailable")
                self.assertEqual(out["withheld_reason_code"], "MALFORMED_FINANCIAL_AMOUNT")
                self.assertIsNone(out["ratio_pct"])
                self.assertFalse(out["risk_calculated"])

    def test_zero_denominator_differs_from_missing_and_never_triggers(self):
        data = facts()
        data[1]["current_amount"] = "-0"
        out = self.compute(data)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["withheld_reason_code"], "ZERO_EQUITY_DENOMINATOR")
        self.assertIsNone(out["comparison_ratio_pct"])
        self.assertIsNone(out["ratio_pct"])
        self.assertIsNone(out["triggered"])
        self.assertFalse(out["risk_calculated"])
        self.assertEqual(out["facts"]["equity"], "-0")

    def test_0_liabilities_calculates_with_no_trigger(self):
        data = facts()
        data[0]["current_amount"] = "0"
        out = self.compute(data)
        self.assertEqual(out["status"], "calculated")
        self.assertEqual(out["ratio_pct"], "0.00")
        self.assertFalse(out["triggered"])

    def test_negative_liabilities_withheld_as_anomaly(self):
        data = facts()
        data[0]["current_amount"] = "-1"
        self.assertEqual(self.compute(data)["status"], "unavailable")

    def test_unverified_or_conflicting_input_never_calculated(self):
        for state in ("conflict", "unavailable", None):
            with self.subTest(state=state):
                data = facts()
                data[0]["state"] = state
                out = self.compute(data)
                self.assertEqual(out["status"], "unavailable")
                self.assertFalse(out["risk_calculated"])
                self.assertIsNone(out["ratio_pct"])

    def test_cross_year_or_statement_is_not_calculated(self):
        for field, value in (("year", 2023), ("fs_div", "OFS")):
            with self.subTest(field=field):
                data = facts()
                data[0][field] = value
                self.assertEqual(self.compute(data)["status"], "unavailable")

    def test_real_manual_evidence_remains_unauthenticated(self):
        data = facts()
        for fact in data:
            fact["source_kind"] = "MANUAL_PRIMARY_SOURCE_VERIFICATION"
        out = calculate_verified_debt_to_equity(data, expected_year=2024)
        self.assertEqual(out["status"], "calculated")
        self.assertFalse(out["authenticated_external_source"])
        self.assertFalse(out["is_demo"])

    def test_synthetic_without_demo_is_rejected(self):
        out = calculate_verified_debt_to_equity(facts(), expected_year=2024)
        self.assertEqual(out["status"], "unavailable")
        self.assertIsNone(out["ratio_pct"])

    def test_extreme_amount_fails_closed_without_crash(self):
        data = facts()
        data[0]["current_amount"] = "9" * 100
        out = self.compute(data)
        self.assertEqual(out["status"], "unavailable")
        self.assertFalse(out["risk_calculated"])

    def test_pure_and_order_invariant(self):
        data = facts()
        original = copy.deepcopy(data)
        self.assertEqual(self.compute(data), self.compute(list(reversed(data))))
        self.assertEqual(data, original)


if __name__ == "__main__":
    unittest.main()
