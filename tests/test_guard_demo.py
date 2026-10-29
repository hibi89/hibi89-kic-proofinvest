"""Offline demonstration contract, including stored audit and human review."""
import tempfile
import unittest
from pathlib import Path

from proofinvest.guard_demo import run_demo


class GuardDemoTests(unittest.TestCase):
    def test_three_decisions_and_verified_review(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = run_demo(Path(directory) / "demo.sqlite")
        self.assertEqual(
            [run["decision"] for run in receipt["runs"]],
            ["HOLD", "REJECT", "APPROVE"],
        )
        self.assertEqual(receipt["runs"][2]["review_action"], "AUTHORIZE_SIMULATION")
        self.assertTrue(receipt["audit_valid"])
        self.assertTrue(receipt["reviews_valid"])
        self.assertFalse(receipt["live_api_called"])
        self.assertFalse(receipt["trade_executed"])
        self.assertTrue(all(not run["trade_executed"] for run in receipt["runs"]))


if __name__ == "__main__":
    unittest.main()
