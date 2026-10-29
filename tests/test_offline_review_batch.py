"""Offline batch orchestration tests: no provider HTTP."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.offline_review_batch import review_capture_batch, format_review_queue_csv, discover_capture_files


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
        self.assertEqual(output["action_counts"]["RECHECK_LOCAL_ARCHIVE"], 2)
        self.assertEqual([x["index"] for x in output["items"]], [0, 1])
        self.assertEqual([x["index"] for x in output["review_queue"]], [0, 1])
        self.assertEqual(output["review_queue"][0]["next_action"], "RECHECK_LOCAL_ARCHIVE")
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

    def test_embedded_summary_is_not_trusted(self):
        with patch("proofinvest.offline_review_batch.replay_local_capture") as replay:
            replay.return_value = {
                "status": "unavailable",
                "reason_code": "REPLAY_DIGEST_CONFLICT",
                "review_summary": {"status": "human_review_required", "review_priority": "normal", "raw_source": "SHOULD_NOT_LEAK"},
            }
            output = review_capture_batch(
                [Path("one.zip")], current_end="2025-09-30",
                prior_end="2024-09-30", needle="revenue",
            )
        self.assertEqual(output["blocked_count"], 1)
        self.assertEqual(output["ready_for_human_review_count"], 0)
        self.assertEqual(output["action_counts"]["RECHECK_LOCAL_ARCHIVE"], 1)
        self.assertNotIn("SHOULD_NOT_LEAK", str(output))

    def test_csv_queue_exports_only_safe_columns(self):
        batch = {"review_queue": [
            {"index": 3, "status": "blocked", "priority": "high",
             "next_action": "RECHECK_LOCAL_ARCHIVE"}]}
        csv_text = format_review_queue_csv(batch)
        self.assertEqual(csv_text,
                         "index,status,priority,next_action\n3,blocked,high,RECHECK_LOCAL_ARCHIVE\n")

    def test_directory_discovery_is_bounded_and_sorted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "b.zip").write_bytes(b"test")
            (root / "a.ZIP").write_bytes(b"test")
            (root / "notes.txt").write_text("ignore")
            self.assertEqual([p.name for p in discover_capture_files(root)], ["a.ZIP", "b.zip"])

    def test_directory_discovery_rejects_empty_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                discover_capture_files(Path(folder))

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
