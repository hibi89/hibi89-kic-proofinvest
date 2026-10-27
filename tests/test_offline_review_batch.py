"""Offline batch orchestration tests: no provider HTTP."""
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.offline_review_batch import review_capture_batch


class BatchReviewTests(unittest.TestCase):
    def test_two_captures_isolated_and_ordered(self):
        with patch("proofinvest.offline_review_batch.replay_local_capture") as replay:
            replay.side_effect = [
                {"status": "unavailable", "reason_code": "REPLAY_DIGEST_CONFLICT"},
                {"status": "unavailable", "reason_code": "ARCHIVED_BYTES_OR_MANIFEST_INVALID"},
            ]
            output = review_capture_batch(
                [Path("one.zip"), Path("two.zip")],
                current_end="2025-09-30", prior_end="2024-09-30", needle="revenue",
            )
        self.assertEqual(output["count"], 2)
        self.assertEqual(output["blocked_count"], 2)
        self.assertEqual([x["index"] for x in output["items"]], [0, 1])
        self.assertNotIn("one.zip", str(output))
        self.assertFalse(output["external_http_called"])

    def test_one_failure_does_not_abort_remaining(self):
        with patch("proofinvest.offline_review_batch.replay_local_capture") as replay:
            replay.side_effect = [
                OSError("failed to read"),
                {"status": "unavailable", "reason_code": "REPLAY_DIGEST_CONFLICT"},
            ]
            output = review_capture_batch(
                [Path("one.zip"), Path("two.zip")],
                current_end="2025-09-30", prior_end="2024-09-30", needle="revenue",
            )
        self.assertEqual(output["count"], 2)
        self.assertEqual(output["items"][0]["summary"]["reason_codes"], ["REPLAY_UNAVAILABLE"])
        self.assertEqual(output["items"][1]["summary"]["reason_codes"], ["REPLAY_DIGEST_CONFLICT"])

    def test_batch_limit(self):
        with self.assertRaises(ValueError):
            review_capture_batch([], current_end="2025-09-30",
                                 prior_end="2024-09-30", needle="revenue")
        with self.assertRaises(ValueError):
            review_capture_batch([Path("a.zip")] * 21,
                                 current_end="2025-09-30",
                                 prior_end="2024-09-30", needle="revenue")


if __name__ == "__main__":
    unittest.main()
