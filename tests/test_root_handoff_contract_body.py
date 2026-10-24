"""Regression guard: a canonical notice cannot mask a wiped handoff contract."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.master_progress import (
    ROOT_CONTRACT_NOTICE, ROOT_CONTRACT_TITLE, validate_root_contract_header,
)

class RootHandoffContractBodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = (ROOT / "KIC_HANDOFF_CONTRACT.md").read_text(encoding="utf-8")

    def test_restored_contract_is_valid(self):
        validate_root_contract_header(self.real)

    def test_lost_body_rejected(self):
        with self.assertRaises(ValueError):
            validate_root_contract_header(ROOT_CONTRACT_NOTICE + "\n\n" + ROOT_CONTRACT_TITLE + "undefined")

    def test_truncated_but_clean_heading_rejected(self):
        with self.assertRaises(ValueError):
            validate_root_contract_header(ROOT_CONTRACT_NOTICE + "\n\n" + ROOT_CONTRACT_TITLE + "\nshort")

    def test_missing_mandatory_section_rejected(self):
        bad = self.real.replace("## 절대로 누락하지 않는 상태 구분", "## removed", 1)
        self.assertNotEqual(bad, self.real)
        with self.assertRaises(ValueError):
            validate_root_contract_header(bad)

    def test_stale_opening_rejected(self):
        with self.assertRaises(ValueError):
            validate_root_contract_header("stale status\n\n" + self.real)

    def test_duplicate_heading_rejected(self):
        with self.assertRaises(ValueError):
            validate_root_contract_header(self.real + "\n" + ROOT_CONTRACT_TITLE)

if __name__ == "__main__":
    unittest.main()
