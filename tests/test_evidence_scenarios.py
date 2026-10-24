"""Reproduce three classifications from one manually reviewed real filing.

No network, private keys, PDF downloads or invented OpenDART responses.
"""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from proofinvest.evidence_scenarios import three_scenarios, verify_growth_claim

EVIDENCE = Path(__file__).resolve().parent.parent / "docs" / "evidence" / "samsung_2024_cfs_revenue.json"


class ActualEvidenceScenariosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def evidence(self):
        return copy.deepcopy(self.original)

    def test_all_three_scenarios_and_explicit_manual_provenance(self):
        results = three_scenarios(self.evidence())
        scenarios = results["scenarios"]
        self.assertEqual(results["mode"], "OFFLINE_MANUAL_EVIDENCE")
        self.assertEqual({k: x["state"] for k, x in scenarios.items()},
                         {"matching_claim":"verified","incorrect_claim":"conflict","no_evidence":"unavailable"})
        self.assertEqual(scenarios["matching_claim"]["computed_pct"], "16.20")
        self.assertEqual(scenarios["incorrect_claim"]["computed_pct"], "16.20")
        self.assertFalse(scenarios["matching_claim"]["dart_viewer_verified"])
        self.assertIn("manually", scenarios["matching_claim"]["verification_scope"])
        self.assertIsNone(scenarios["no_evidence"]["source_url"])

    def test_no_input_mutation_or_network_calls(self):
        evidence = self.evidence()
        before = copy.deepcopy(evidence)
        self.assertEqual(three_scenarios(evidence), three_scenarios(evidence))
        self.assertEqual(evidence, before)

    def test_wrong_claim_and_malformed_claim_distinguished(self):
        self.assertEqual(verify_growth_claim(self.evidence(),"25")["state"],"conflict")
        self.assertEqual(verify_growth_claim(self.evidence(),"not-a-number")["state"],"unavailable")
        self.assertEqual(verify_growth_claim(self.evidence(),None)["state"],"unavailable")

    def test_missing_evidence_fails_closed(self):
        self.assertEqual(verify_growth_claim(None,"16.2")["state"],"unavailable")
        self.assertEqual(verify_growth_claim({},"16.2")["state"],"unavailable")

    def test_tampered_amount_not_accepted_without_recalculation(self):
        evidence = self.evidence()
        evidence["current"]["amount"] = "330870903"
        self.assertEqual(verify_growth_claim(evidence,"16.20")["state"],"unavailable")
        self.assertIn("disagrees",verify_growth_claim(evidence,"16.20")["reason"])

    def test_mixed_period_or_statement_fails_closed(self):
        evidence = self.evidence()
        evidence["previous"]["fiscal_year"] = 2022
        self.assertEqual(verify_growth_claim(evidence,"16.20")["state"],"unavailable")
        evidence = self.evidence()
        evidence["financial_statement"] = "OFS"
        self.assertEqual(verify_growth_claim(evidence,"16.20")["state"],"unavailable")
        evidence = self.evidence()
        evidence["previous"]["period_end"] = "2023-09-30"
        self.assertEqual(verify_growth_claim(evidence,"16.20")["state"],"unavailable")

    def test_unit_or_metric_or_source_quality_fails_closed(self):
        for name, value in (("unit","USD"),("metric","operating_profit"),("report_type","Q1")):
            with self.subTest(name=name):
                evidence = self.evidence()
                evidence[name] = value
                self.assertEqual(verify_growth_claim(evidence,"16.20")["state"],"unavailable")
        evidence = self.evidence()
        evidence["primary_source"]["visual_verified"] = False
        self.assertEqual(verify_growth_claim(evidence,"16.20")["state"],"unavailable")
        evidence = self.evidence()
        evidence["primary_source"]["url"] = "http://invalid.test/source.pdf"
        self.assertEqual(verify_growth_claim(evidence,"16.20")["state"],"unavailable")

    def test_zero_denominator_does_not_derive_growth(self):
        evidence = self.evidence()
        evidence["previous"]["amount"] = "0"
        self.assertEqual(verify_growth_claim(evidence,"16.20")["state"],"unavailable")

    def test_real_source_link_retained_for_conflict(self):
        result = verify_growth_claim(self.evidence(),"30")
        self.assertEqual(result["state"],"conflict")
        self.assertTrue(result["source_url"].startswith("https://images.samsung.com/"))
        self.assertEqual(result["claim_pct"],"30")
        self.assertEqual(result["unit"],"KRW_MILLIONS")

    def test_cli_outputs_machine_readable_three_scenarios(self):
        result = subprocess.run(
            [sys.executable,"-m","proofinvest.evidence_scenarios"],
            capture_output=True,text=True,check=True,
        )
        output = json.loads(result.stdout)
        self.assertEqual(output["scenarios"]["matching_claim"]["state"],"verified")
        self.assertEqual(output["scenarios"]["incorrect_claim"]["state"],"conflict")
        self.assertEqual(output["scenarios"]["no_evidence"]["state"],"unavailable")


if __name__ == "__main__":
    unittest.main()
