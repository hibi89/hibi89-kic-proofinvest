"""Fail-closed Risk input gate, synthetic only; no API and no investment decision."""
import copy
import unittest

from proofinvest.risk import gate_verified_risk_inputs
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


if __name__ == "__main__":
    unittest.main()
