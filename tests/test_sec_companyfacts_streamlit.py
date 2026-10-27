"""Streamlit SEC annual-revenue workflow: offline only, not live API."""
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
SEC_SOURCE = "Apple SEC 10-K 수동 발췌 — 오프라인 검산 (2025/2024)"


def sec_screen():
    at = AppTest.from_file(str(APP)).run(timeout=15)
    at.selectbox[0].set_value(SEC_SOURCE).run(timeout=15)
    return at


class SecStreamlitTests(unittest.TestCase):
    def test_curated_post_filing_example_calculates_but_never_authenticates(self):
        at = sec_screen()
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("MANUALLY_CURATED_SEC_EXCERPT" in w.value for w in at.warning))
        self.assertTrue(any(m.label == "연매출 성장률 (오프라인 수치검산)"
                            and m.value == "6.43%" for m in at.metric))
        self.assertTrue(any("실 API/LLM 0회" in x.value for x in at.caption))
        self.assertFalse(any(m.label == "부채/자본 비율" for m in at.metric))

    def test_point_in_time_pre_filing_blocks_calculation(self):
        at = sec_screen()
        at.selectbox[1].set_value("2025-10-30 — 공시 공개 전").run(timeout=15)
        self.assertFalse(at.exception)
        self.assertTrue(any("FILING_AFTER_AS_OF" in w.value for w in at.warning))
        self.assertFalse(any(m.label == "연매출 성장률 (오프라인 수치검산)" for m in at.metric))

    def test_claim_conflict_is_visible_and_not_authenticated(self):
        at = sec_screen()
        at.selectbox[2].set_value("30% — 불일치 주장").run(timeout=15)
        self.assertFalse(at.exception)
        self.assertTrue(any("불일치" in e.value for e in at.error))
        self.assertTrue(any(m.value == "6.43%" for m in at.metric))

    def test_existing_default_source_is_still_synthetic(self):
        at = AppTest.from_file(str(APP)).run(timeout=15)
        self.assertFalse(at.exception)
        self.assertIn("SYNTHETIC_FIXTURE", at.warning[0].value)


if __name__ == "__main__":
    unittest.main()
