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
        self.assertEqual(receipt["audited_run_count"], 4)
        self.assertEqual(
            receipt["source_kind"],
            "MIXED_SYNTHETIC_AND_MANUALLY_CURATED_UNAUTHENTICATED",
        )
        self.assertEqual(
            receipt["curated_sec"]["source_kind"],
            "HUMAN_CURATED_FROM_PUBLIC_SEC_10K_NOT_RAW_API",
        )
        self.assertEqual(receipt["curated_sec"]["status"], "calculated_unverified")
        self.assertEqual(receipt["curated_sec"]["guard_decision"], "HOLD")
        self.assertFalse(receipt["curated_sec"]["external_source_authenticated"])
        self.assertFalse(receipt["curated_sec"]["trade_executed"])
        self.assertTrue(receipt["audit_valid"])
        self.assertTrue(receipt["reviews_valid"])
        self.assertFalse(receipt["live_api_called"])
        self.assertFalse(receipt["trade_executed"])
        self.assertTrue(all(not run["trade_executed"] for run in receipt["runs"]))


if __name__ == "__main__":
    unittest.main()
