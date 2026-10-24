"""Keep the repository entrypoint aligned with active single-lead routing.

Historical worker docs are preserved, but README must never dispatch KIC-R-001.
Pure offline test; no external GitHub requests or deployment required.
"""
import unittest
from pathlib import Path


README = Path(__file__).resolve().parents[1] / "README.md"


class CurrentReadmeRoutingTests(unittest.TestCase):
    def test_readme_points_to_single_source_of_truth(self):
        text = README.read_text(encoding="utf-8")
        for path in (
            "CHAT_BOOTSTRAP.md",
            "KIC_RESUME_STATE.md",
            "docs/roles/lead/LEAD_ACTIVE_WORK.md",
            "docs/roles/lead/MASTER_PROGRESS.json",
        ):
            with self.subTest(path=path):
                self.assertIn(path, text)

    def test_readme_does_not_reactivate_legacy_worker_dispatch(self):
        text = README.read_text(encoding="utf-8")
        self.assertNotIn("현재 READY KIC-R-001", text)
        self.assertNotIn("날짜별 11 DONE / 2 BLOCKED / 47 NOT_STARTED", text)
        self.assertIn("폐기된 이력", text)
        self.assertIn("lead/kic", text)


if __name__ == "__main__":
    unittest.main()
