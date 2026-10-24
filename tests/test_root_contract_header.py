"""Prevent stale 60-day percentages from being copied into the root handoff contract."""
import unittest

from scripts.master_progress import (
    ROOT, ROOT_CONTRACT_NOTICE, ROOT_CONTRACT_TITLE,
    validate_root_contract_header,
)


class RootContractHeaderIntegrityTests(unittest.TestCase):
    def test_actual_live_root_contract_is_link_only(self):
        text = (ROOT / "KIC_HANDOFF_CONTRACT.md").read_text(encoding="utf-8")
        validate_root_contract_header(text)

    def test_header_does_not_store_status_dates_or_counts(self):
        self.assertIn("MASTER_PROGRESS.json", ROOT_CONTRACT_NOTICE)
        self.assertIn("MASTER_PROGRESS.md", ROOT_CONTRACT_NOTICE)
        self.assertNotIn("2026-11-06", ROOT_CONTRACT_NOTICE)
        self.assertNotIn("11 DONE", ROOT_CONTRACT_NOTICE)

    def test_old_duplicate_completion_snapshot_fails(self):
        forged = (
            "> Snapshot: 11 DONE / 2 BLOCKED / 47 NOT_STARTED; NEXT 2026-11-06\n\n"
            + ROOT_CONTRACT_TITLE + "\ncontract body"
        )
        with self.assertRaisesRegex(ValueError, "canonical link-only"):
            validate_root_contract_header(forged)

    def test_missing_or_duplicate_heading_is_rejected(self):
        for txt in (ROOT_CONTRACT_NOTICE, ROOT_CONTRACT_NOTICE + "\n" + ROOT_CONTRACT_TITLE * 2):
            with self.subTest(text=txt[:50]):
                with self.assertRaisesRegex(ValueError, "heading"):
                    validate_root_contract_header(txt)

    def test_future_append_to_contract_body_preserves_header(self):
        # Future additions must extend a valid policy, not replace its required body.
        original = (ROOT / "KIC_HANDOFF_CONTRACT.md").read_text(encoding="utf-8")
        future = original + "\n\n## Future operational notes\n" + ("Preserve required policy sections.\n" * 3)
        validate_root_contract_header(future)

    def test_arbitrary_long_notes_cannot_replace_policy_body(self):
        forged = ROOT_CONTRACT_NOTICE + "\n\n" + ROOT_CONTRACT_TITLE + "\n" + ("old notes\n" * 3000)
        with self.assertRaisesRegex(ValueError, "body missing or corrupted"):
            validate_root_contract_header(forged)


if __name__ == "__main__":
    unittest.main()
