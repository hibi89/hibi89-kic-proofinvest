"""P53 offline scenario regressions with actual Engine C integration."""
import copy
import unittest
from unittest.mock import patch

from proofinvest.industry_scenarios import build_industry_scenarios
from proofinvest.industry_vision import analyze_industry_vision
from test_industry_vision import fixture


class IndustryScenariosTests(unittest.TestCase):
    def test_engine_c_end_to_end_real_calculation_synthetic(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")) as net:
            report = analyze_industry_vision(fixture())
        net.assert_not_called()
        cards = report["conditional_scenarios"]
        self.assertEqual([x["id"] for x in cards],
                         ["OBSERVED_BASE", "CONDITIONAL_UPSIDE", "CONDITIONAL_DOWNSIDE"])
        self.assertIn("15.00%", cards[0]["explanation"])
        self.assertIn("20.00%", cards[0]["explanation"])
        self.assertIn("30.00%", cards[0]["explanation"])
        self.assertEqual(set(cards[0]["source_ids"]),
                         {"target-old", "target-now", "peer-old", "peer-now",
                          "sector-old", "sector-now"})
        self.assertEqual(cards[1]["source_ids"], ["sector-now"])
        self.assertEqual(cards[2]["kind"], "WITHHELD_NO_DRIVER")
        self.assertTrue(all(c["future_return_forecast_pct"] is None for c in cards))
        self.assertTrue(all(c["verified"] is False for c in cards))
        self.assertFalse(report["ai_generated"])
        self.assertFalse(report["guard_decision_changed"])

    def test_no_driver_does_not_fabricate_outlook(self):
        payload = fixture()
        payload["drivers"] = []
        cards = analyze_industry_vision(payload)["conditional_scenarios"]
        self.assertEqual([c["kind"] for c in cards[1:]], ["WITHHELD_NO_DRIVER"] * 2)
        self.assertTrue(all(not c["source_ids"] for c in cards[1:]))

    def test_zero_denominator_withholds_comparison(self):
        payload = fixture()
        payload["target"]["prior_revenue_usd"] = "0"
        payload["industry_series"]["prior_value"] = "0"
        self.assertIn("보류", analyze_industry_vision(payload)["conditional_scenarios"][0]["explanation"])

    def test_mixed_direction_is_conditional_in_both(self):
        payload = fixture()
        payload["drivers"][0]["direction"] = "MIXED"
        cards = analyze_industry_vision(payload)["conditional_scenarios"]
        self.assertEqual(cards[1]["kind"], "CONDITIONAL_OPERATOR_HYPOTHESIS")
        self.assertEqual(cards[2]["kind"], "CONDITIONAL_OPERATOR_HYPOTHESIS")
        self.assertEqual(cards[2]["source_ids"], ["sector-now"])

    def test_source_link_or_fake_auth_rejected_without_ai(self):
        report = analyze_industry_vision(fixture())
        for change in ("bad_schema", "fake_auth", "missing_source", "duplicate_source", "bad_growth"):
            bad = copy.deepcopy(report)
            if change == "bad_schema": bad["schema"] = "other"
            if change == "fake_auth": bad["source_authenticated"] = True
            if change == "missing_source": bad["vision_drivers"][0]["source_ids"] = ["no-source"]
            if change == "duplicate_source": bad["sources"][1]["id"] = bad["sources"][0]["id"]
            if change == "bad_growth": bad["target"]["growth_pct_reported_input"] = "NaN"
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_industry_scenarios(bad)


if __name__ == "__main__":
    unittest.main()
