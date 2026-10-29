"""SEC Guard adapter integration contract tests."""
import unittest
from proofinvest.guard_sec_adapter import evaluate_sec_guard


class SECGuardAdapterTests(unittest.TestCase):
    def test_matching_sec_numbers_hold_without_risk(self):
        result = evaluate_sec_guard({"status": "calculated_unverified"})
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertFalse(result["external_source_authenticated"])

    def test_conflict_rejected(self):
        self.assertEqual(evaluate_sec_guard({"status": "conflict"})["guard"]["decision"], "REJECT")

    def test_unavailable_held(self):
        self.assertEqual(evaluate_sec_guard({"status": "unavailable"})["guard"]["decision"], "HOLD")

    def test_unknown_status_held(self):
        self.assertEqual(evaluate_sec_guard({"status": "unexpected"})["guard"]["decision"], "HOLD")

    def test_only_verified_with_risk_may_approve(self):
        result = evaluate_sec_guard({"status": "calculated_unverified"}, risk={
            "risk_calculated": True, "comparison_ratio_pct": "100"})
        self.assertEqual(result["guard"]["decision"], "APPROVE")
        self.assertFalse(result["guard"]["human_approved"])


if __name__ == "__main__":
    unittest.main()
