"""Authoritative next-task handoff marker; offline and deterministic."""
import json
from pathlib import Path
import unittest
from scripts.master_progress import DATA, ROOT, validate_handoff_pointer

MARK = "<!-- KIC_CANONICAL_NEXT_TASK_DATE: 2026-12-03 -->"


class HandoffPointerIntegrityTests(unittest.TestCase):
    def test_single_marker_matches_ledger(self):
        validate_handoff_pointer(MARK, "2026-12-03")

    def test_very_long_prepended_audit_history_is_safe(self):
        history = ("Previous 2026-11-30\n" * 1000) + MARK
        self.assertGreater(len(history), 2500)
        validate_handoff_pointer(history, "2026-12-03")

    def test_unmarked_date_is_not_authoritative(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            validate_handoff_pointer("Next task 2026-12-03", "2026-12-03")

    def test_stale_marker_is_rejected_even_when_date_appears_elsewhere(self):
        old = "<!-- KIC_CANONICAL_NEXT_TASK_DATE: 2026-11-30 -->\nNEXT 2026-12-03"
        with self.assertRaisesRegex(ValueError, "mismatch"):
            validate_handoff_pointer(old, "2026-12-03")

    def test_multiple_markers_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            validate_handoff_pointer(MARK + "\n" + MARK, "2026-12-03")

    def test_malformed_marker_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            validate_handoff_pointer("<!-- KIC_CANONICAL_NEXT_TASK_DATE: tomorrow -->", "2026-12-03")

    def test_three_actual_handoffs_match_canonical_json(self):
        day = json.loads(Path(DATA).read_text(encoding="utf-8"))["next_task_date"]
        for rel in ("KIC_RESUME_STATE.md", "CHAT_BOOTSTRAP.md", "docs/roles/lead/LEAD_ACTIVE_WORK.md"):
            with self.subTest(rel=rel):
                validate_handoff_pointer((ROOT / rel).read_text(encoding="utf-8"), day, rel)


if __name__ == "__main__":
    unittest.main()
