"""End-to-end offline Guard workflow tests."""
import tempfile
import unittest
from pathlib import Path

from proofinvest.guard_workflow import run_guard_review
from proofinvest.guard_audit import GuardAuditStore

RISK = {"risk_calculated": True, "comparison_ratio_pct": "100"}


class GuardWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "guard.sqlite"

    def test_sec_without_risk_is_hold_and_audited(self):
        result = run_guard_review({"status": "calculated_unverified"}, run_id="hold-1", database_path=self.db)
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertFalse(result["trade_executed"])

    def test_conflict_rejects_simulation(self):
        with self.assertRaises(ValueError):
            run_guard_review({"status": "conflict"}, run_id="reject-1",
                             database_path=self.db, risk=RISK,
                             reviewer="human", action="AUTHORIZE_SIMULATION",
                             reason="Attempt rejected review")
        self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_explicit_simulated_review(self):
        result = run_guard_review({"status": "calculated_unverified"}, run_id="demo-1",
                                  database_path=self.db, risk=RISK,
                                  reviewer="human", action="AUTHORIZE_SIMULATION",
                                  reason="Synthetic-only approval for demonstration")
        self.assertEqual(result["guard"]["decision"], "APPROVE")
        self.assertEqual(result["review"]["action"], "AUTHORIZE_SIMULATION")
        self.assertFalse(result["trade_executed"])

    def test_idempotent_replay(self):
        first = run_guard_review({"status": "unavailable"}, run_id="same", database_path=self.db)
        second = run_guard_review({"status": "unavailable"}, run_id="same", database_path=self.db)
        self.assertFalse(first["audit"]["replayed"])
        self.assertTrue(second["audit"]["replayed"])

    def test_changed_inputs_fail_closed(self):
        run_guard_review({"status": "unavailable"}, run_id="same", database_path=self.db)
        with self.assertRaises(ValueError):
            run_guard_review({"status": "conflict"}, run_id="same", database_path=self.db)


if __name__ == "__main__":
    unittest.main()
