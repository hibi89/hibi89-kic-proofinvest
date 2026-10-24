"""Manual issuer Streamlit mode smoke tests (no network and no real API)."""
from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
SOURCE = "삼성전자 공개 재무제표 수동검산 (2024/2023)"


def manual_app():
    at = AppTest.from_file(str(APP)).run(timeout=15)
    at.selectbox[0].set_value(SOURCE).run(timeout=15)
    return at


class ManualIssuerStreamlitTests(unittest.TestCase):
    def test_default_synthetic_mode_unchanged(self):
        at = AppTest.from_file(str(APP)).run(timeout=15)
        self.assertFalse(at.exception)
        self.assertTrue(at.warning)
        self.assertIn("SYNTHETIC_FIXTURE", at.warning[0].value)
        self.assertEqual(at.radio[0].label, "조회 방식")

    def test_manual_mode_shows_historical_provenance_and_withheld_risk(self):
        at = manual_app()
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertIn("실제 발행사 수동기록", at.title[0].value)
        self.assertIn("MANUAL_PRIMARY_SOURCE_VERIFICATION", at.warning[0].value)
        self.assertTrue(any(m.label == "외부 원문 독립 인증" and m.value == "미인증" for m in at.metric))
        self.assertTrue(any(m.label == "매출 성장률(수동기록 계산)" and m.value == "16.20%" for m in at.metric))
        self.assertFalse(any(m.label == "부채/자본 비율" for m in at.metric))
        self.assertTrue(any("Risk 산출 보류" in x.value for x in at.info))

    def test_matching_claim_is_only_manual_numeric_agreement(self):
        at = manual_app()
        self.assertTrue(any("원문 진위 인증이 아닙니다" in x.value for x in at.success))
        self.assertTrue(any("DART" in x.value for x in at.warning))

    def test_conflicting_claim_shows_error_and_still_withholds_risk(self):
        at = manual_app()
        at.selectbox[1].set_value("30% — 불일치 사례").run(timeout=15)
        self.assertFalse(at.exception)
        self.assertTrue(any("불일치" in e.value for e in at.error))
        self.assertFalse(any(m.label == "부채/자본 비율" for m in at.metric))
        self.assertTrue(any("Risk 산출 보류" in x.value for x in at.info))

    def test_missing_claim_is_not_falsely_verified(self):
        at = manual_app()
        at.selectbox[1].set_value("주장 없음 — 판정 보류").run(timeout=15)
        self.assertFalse(at.exception)
        self.assertTrue(any("검증 보류" in w.value for w in at.warning))
        self.assertFalse(at.success)

    def test_manual_mode_has_issuer_link_but_no_dart_verified_claim(self):
        at = manual_app()
        self.assertTrue(any("발행기관 IR 게시 페이지" in x.value for x in at.markdown))
        self.assertTrue(any("AI/LLM" in x.value for x in at.caption))
        self.assertTrue(any("2025-02-18" in x.value for x in at.info))
        self.assertFalse(at.exception)


if __name__ == "__main__":
    unittest.main()
