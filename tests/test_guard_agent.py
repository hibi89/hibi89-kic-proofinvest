"""Guard rules are local simulation only."""
import unittest

from proofinvest.guard_agent import evaluate_guard


POLICY = {"mode": "DEMO_POLICY", "version": "1", "max_debt_to_equity_pct": "200"}
RISK = {"risk_calculated": True, "comparison_ratio_pct": "199.999"}
GOOD = {"status": "VERIFIED", "source_kind": "SYNTHETIC_FIXTURE"}


class GuardAgentTests(unittest.TestCase):
    def test_eligible_not_executed(self):
        result = evaluate_guard([GOOD], policy=POLICY, risk=RISK)
        self.assertEqual(result["decision"], "APPROVE")
        self.assertFalse(result["human_approved"])
        self.assertFalse(result["trade_executed"])

    def test_conflict_rejected(self):
        result = evaluate_guard([{**GOOD, "status": "CONFLICT"}], policy=POLICY, risk=RISK)
        self.assertEqual(result["decision"], "REJECT")

    def test_unavailable_held(self):
        result = evaluate_guard([{**GOOD, "status": "UNAVAILABLE"}], policy=POLICY, risk=RISK)
        self.assertEqual(result["decision"], "HOLD")

    def test_policy_limit(self):
        result = evaluate_guard([GOOD], policy=POLICY, risk={"risk_calculated": True, "comparison_ratio_pct": "200.001"})
        self.assertEqual(result["decision"], "REJECT")

    def test_missing_risk(self):
        self.assertEqual(evaluate_guard([GOOD], policy=POLICY)["decision"], "HOLD")

    def test_invalid_policy(self):
        self.assertEqual(evaluate_guard([GOOD], policy={"mode": "DEMO_POLICY"}, risk=RISK)["decision"], "HOLD")

    def test_mixed_claims(self):
        result = evaluate_guard([GOOD, {**GOOD, "status": "CONFLICT"}], policy=POLICY, risk=RISK)
        self.assertEqual(result["decision"], "REJECT")

    def test_float_is_not_accepted(self):
        result = evaluate_guard([GOOD], policy=POLICY, risk={"risk_calculated": True, "comparison_ratio_pct": 100.0})
        self.assertEqual(result["decision"], "HOLD")

    def test_untrusted_source_held(self):
        result = evaluate_guard([{**GOOD, "source_kind": "SEC_AUTHENTICATED"}], policy=POLICY, risk=RISK)
        self.assertEqual(result["decision"], "HOLD")


if __name__ == "__main__":
    unittest.main()
