"""P89 independent Engine B Streamlit and provenance-safety regressions."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from proofinvest.sec_web_accounting_signals import triage_manual_sec_web
from proofinvest.sec_web_accounting_ui import validate_engine_b_review

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
SOURCE = "KUODRA · Apple SEC 웹텍스트 수동검산 → Guard (오프라인)"


class AccountingUI(unittest.TestCase):
    def test_good_data_and_forgery_blocked(self):
        source = triage_manual_sec_web()
        validate_engine_b_review(source)
        for section, k, value in (
            ("top", "source_authenticated", True),
            ("top", "misconduct_proven", True),
            ("top", "review_prompt_count", 4),
            ("prompt", "value_pp", "100"),
            ("prompt", "review", False),
        ):
            with self.subTest(k=k):
                forged = deepcopy(source)
                (forged["prompts"][0] if section == "prompt" else forged)[k] = value
                with self.assertRaisesRegex(ValueError, "WEB_B_UI_UNTRUSTED"):
                    validate_engine_b_review(forged)

    def test_engine_b_click_requires_intent_and_does_not_run_guard(self):
        from streamlit.testing.v1 import AppTest
        a = AppTest.from_file(str(APP)).run(timeout=20)
        with patch("proofinvest.sec_web_accounting_signals.triage_manual_sec_web",
                   side_effect=AssertionError("NO_AUTO_RUN")) as calc:
            a.selectbox[0].set_value(SOURCE).run(timeout=20)
        calc.assert_not_called()
        self.assertFalse(a.exception, [str(e.message) for e in a.exception])
        self.assertEqual(len(a.button), 2)
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_EXTERNAL_HTTP")) as http:
            a.button[1].click().run(timeout=25)
        http.assert_not_called()
        self.assertFalse(a.exception, [str(e.message) for e in a.exception])
        self.assertTrue(any(m.label == "회계 검토 질문 · 이상행위 확정 아님"
                            and m.value == "3건" for m in a.metric))
        self.assertFalse(any(m.label == "데모 Guard 판정" for m in a.metric))

    def test_invalid_source_fail_closed(self):
        from streamlit.testing.v1 import AppTest
        a = AppTest.from_file(str(APP)).run(timeout=20)
        a.selectbox[0].set_value(SOURCE).run(timeout=20)
        with patch("proofinvest.sec_web_accounting_signals.triage_manual_sec_web",
                   side_effect=ValueError("WEB_B_SOURCE_NOT_TRUSTED")):
            a.button[1].click().run(timeout=20)
        self.assertFalse(a.exception, [str(e.message) for e in a.exception])
        self.assertTrue(any("결과를 차단" in e.value for e in a.error))

    def test_existing_guard_remains_first_button(self):
        from streamlit.testing.v1 import AppTest
        a = AppTest.from_file(str(APP)).run(timeout=20)
        a.selectbox[0].set_value(SOURCE).run(timeout=20)
        with patch("proofinvest.sec_web_accounting_signals.triage_manual_sec_web",
                   side_effect=AssertionError("NO_ENGINE_B_ON_GUARD")) as calc:
            a.button[0].click().run(timeout=20)
        calc.assert_not_called()
        self.assertFalse(a.exception, [str(e.message) for e in a.exception])
        self.assertTrue(any(m.label == "데모 Guard 판정" and m.value == "REJECT"
                            for m in a.metric))


if __name__ == "__main__":
    unittest.main()
