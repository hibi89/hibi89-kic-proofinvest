"""Guard human review is explicitly separate from verification and execution."""
import tempfile
import unittest
from pathlib import Path

from proofinvest.guard_agent import evaluate_guard
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.guard_review import GuardReviewStore

POLICY = {"mode": "DEMO_POLICY", "version": "1", "max_debt_to_equity_pct": "200"}
RISK = {"risk_calculated": True, "comparison_ratio_pct": "100"}


class HumanReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / "review.sqlite"
        self.audit = GuardAuditStore(path)
        self.review = GuardReviewStore(path)

    def record(self, run_id, status):
        decision = evaluate_guard(
            [{"status": status, "source_kind": "SYNTHETIC_FIXTURE"}],
            policy=POLICY, risk=RISK,
        )
        self.audit.record_decision(run_id, {"claim": status}, decision)

    def test_eligible_simulation_only(self):
        self.record("good", "VERIFIED")
        result = self.review.record_review("good", "reviewer", "AUTHORIZE_SIMULATION", "Reviewed synthetic facts")
        self.assertEqual(result["decision"], "APPROVE")
        self.assertFalse(result["trade_executed"])
        self.assertTrue(self.audit.verify_chain())

    def test_conflict_cannot_be_overridden(self):
        self.record("bad", "CONFLICT")
        with self.assertRaises(ValueError):
            self.review.record_review("bad", "reviewer", "AUTHORIZE_SIMULATION", "Cannot override conflict")

    def test_unavailable_cannot_be_overridden(self):
        self.record("unknown", "UNAVAILABLE")
        with self.assertRaises(ValueError):
            self.review.record_review("unknown", "reviewer", "AUTHORIZE_SIMULATION", "Missing source evidence")

    def test_exception_request_not_approval(self):
        self.record("bad", "CONFLICT")
        result = self.review.record_review("bad", "reviewer", "REQUEST_EXCEPTION", "Please recheck disputed data")
        self.assertEqual(result["decision"], "REJECT")
        self.assertFalse(result["trade_executed"])

    def test_missing_reason_fails(self):
        self.record("good", "VERIFIED")
        with self.assertRaises(ValueError):
            self.review.record_review("good", "reviewer", "AUTHORIZE_SIMULATION", " ")

    def test_unknown_run_fails(self):
        with self.assertRaises(ValueError):
            self.review.record_review("missing", "reviewer", "ACKNOWLEDGE", "Reviewed no record")


if __name__ == "__main__":
    unittest.main()
