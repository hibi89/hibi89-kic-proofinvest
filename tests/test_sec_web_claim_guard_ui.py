"""P79 actual Streamlit reviewer interactions for manual SEC WEB -> demo Guard."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from proofinvest.sec_web_claim_guard_demo import review_manual_web_growth_claim
from proofinvest.sec_web_claim_guard_ui import (
    validate_manual_web_guard_ui_result, _CHOICES,
)

_SOURCE = "KUODRA · Apple SEC 웹텍스트 수동검산 → Guard (오프라인)"
_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


class ManualWebGuardUITests(unittest.TestCase):
    def test_valid_replay_and_forgeries_refused_before_render(self):
        for claim in ("30", "6.43", None):
            with self.subTest(claim=claim):
                result = review_manual_web_growth_claim(claim)
                validate_manual_web_guard_ui_result(result, claim)
                result["source_authenticated"] = True
                with self.assertRaisesRegex(ValueError, "WEB_GUARD_UI_UNTRUSTED"):
                    validate_manual_web_guard_ui_result(result, claim)

    def test_no_change_to_default_first_run(self):
        from streamlit.testing.v1 import AppTest
        a = AppTest.from_file(str(_APP)).run(timeout=20)
        self.assertFalse(a.exception, [str(x.message) for x in a.exception])
        self.assertTrue(a.title)
        self.assertIn("오프라인 합성 데이터", a.title[0].value)
        self.assertFalse(any(m.label == "데모 Guard 판정" for m in a.metric))

    def test_manual_sec_web_mode_requires_click_and_zero_http(self):
        from streamlit.testing.v1 import AppTest
        with patch("urllib.request.urlopen", side_effect=AssertionError("HTTP_FORBIDDEN")) as http:
            a = AppTest.from_file(str(_APP)).run(timeout=20)
            with patch("proofinvest.sec_web_claim_guard_ui.review_manual_web_growth_claim",
                       side_effect=AssertionError("RUN_MUST_BE_CLICKED")) as calc:
                a.selectbox[0].set_value(_SOURCE).run(timeout=20)
            calc.assert_not_called()
            http.assert_not_called()
        self.assertFalse(a.exception, [str(x.message) for x in a.exception])
        self.assertTrue(any("SEC_RENDERED_WEB_TEXT" in w.value for w in a.warning))
        self.assertFalse(any(m.label == "데모 Guard 판정" for m in a.metric))

    def test_all_three_clicks_render_guard_not_authenticated_data(self):
        from streamlit.testing.v1 import AppTest
        for choice, target in zip(list(_CHOICES), ("REJECT", "HOLD", "HOLD")):
            with self.subTest(choice=choice):
                a = AppTest.from_file(str(_APP)).run(timeout=20)
                a.selectbox[0].set_value(_SOURCE).run(timeout=20)
                a.selectbox[1].set_value(choice).run(timeout=20)
                with patch("urllib.request.urlopen",
                           side_effect=AssertionError("HTTP_FORBIDDEN")) as http:
                    a.button[0].click().run(timeout=25)
                http.assert_not_called()
                self.assertFalse(a.exception, [str(x.message) for x in a.exception])
                self.assertTrue(any(m.label == "데모 Guard 판정" and m.value == target
                                    for m in a.metric))
                self.assertTrue(any("SEC_RENDERED_WEB_TEXT" in w.value for w in a.warning))
                self.assertFalse(any(m.value == "인증" for m in a.metric))

    def test_tampered_result_fails_closed_in_actual_streamlit(self):
        from streamlit.testing.v1 import AppTest
        forged = review_manual_web_growth_claim("30")
        forged["source_authenticated"] = True
        a = AppTest.from_file(str(_APP)).run(timeout=20)
        a.selectbox[0].set_value(_SOURCE).run(timeout=20)
        with patch("proofinvest.sec_web_claim_guard_ui.review_manual_web_growth_claim",
                   return_value=forged):
            a.button[0].click().run(timeout=20)
        self.assertFalse(a.exception, [str(x.message) for x in a.exception])
        self.assertTrue(any("결과를 차단" in e.value for e in a.error))
        self.assertFalse(any(m.label == "데모 Guard 판정" for m in a.metric))


if __name__ == "__main__":
    unittest.main()
