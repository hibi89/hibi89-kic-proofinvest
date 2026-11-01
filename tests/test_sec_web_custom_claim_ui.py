"""P84: arbitrary human growth assertion through the existing offline Guard UI."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from proofinvest.sec_web_claim_guard_demo import review_manual_web_growth_claim
from proofinvest.sec_web_claim_guard_ui import (
    _CUSTOM, _expected_for_claim, validate_manual_web_guard_ui_result,
)

_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_SOURCE = "KUODRA · Apple SEC 웹텍스트 수동검산 → Guard (오프라인)"


class CustomManualWebGrowthClaimTests(unittest.TestCase):
    def test_custom_numbers_feed_existing_guard_and_calculate_delta(self):
        for claim, delta, state, decision in (
            ("10.00", "3.57", "CONFLICT", "REJECT"),
            ("8.25", "1.82", "CONFLICT", "REJECT"),
            ("-100.00", "-106.43", "CONFLICT", "REJECT"),
            ("6.43", "0.00", "VERIFIED", "HOLD"),
            ("6.4", "-0.03", "CONFLICT", "REJECT"),
            ("999.99", "993.56", "CONFLICT", "REJECT"),
        ):
            with self.subTest(claim=claim), patch(
                "urllib.request.urlopen", side_effect=AssertionError("HTTP_NOT_ALLOWED")
            ) as http:
                result = review_manual_web_growth_claim(claim)
                validate_manual_web_guard_ui_result(result, claim)
                http.assert_not_called()
                self.assertEqual(result["numeric_verdict"], state)
                self.assertEqual(result["claim_minus_manual_web_pp"], delta)
                self.assertEqual(result["guard"]["decision"], decision)
                self.assertFalse(result["source_authenticated"])
                self.assertFalse(result["persistent_audit_written"])
                self.assertFalse(result["trade_executed"])

    def test_malformed_or_injection_input_does_not_read_source(self):
        for claim in ("", "NaN", "Infinity", "10e2", "0<script>",
                      "6.430", "1000", "-100.01", " 8", "+8", "8;rm", "8,25", 8, True):
            with self.subTest(claim=repr(claim)):
                with self.assertRaises(ValueError):
                    _expected_for_claim(claim)
                with patch(
                    "proofinvest.sec_web_claim_guard_demo.build_web_only_brief",
                    side_effect=AssertionError("SOURCE_SHOULD_NOT_BE_READ"),
                ) as source:
                    with self.assertRaises(ValueError):
                        review_manual_web_growth_claim(claim)
                    source.assert_not_called()

    def test_forged_result_or_approval_cannot_be_displayed(self):
        valid = review_manual_web_growth_claim("8.25")
        for key, value in (
            ("claim_minus_manual_web_pp", "0.00"),
            ("claim_growth_pct", "6.43"),
            ("numeric_verdict", "VERIFIED"),
            ("source_authenticated", True),
            ("real_sec_a_b_c_end_to_end_verified", True),
        ):
            with self.subTest(key=key):
                fake = deepcopy(valid)
                fake[key] = value
                with self.assertRaisesRegex(ValueError, "WEB_GUARD_UI_UNTRUSTED_RESULT"):
                    validate_manual_web_guard_ui_result(fake, "8.25")
        fake = deepcopy(valid)
        fake["guard"]["decision"] = "APPROVE"
        with self.assertRaisesRegex(ValueError, "WEB_GUARD_UI_UNTRUSTED_RESULT"):
            validate_manual_web_guard_ui_result(fake, "8.25")

    def test_streamlit_custom_click_and_no_external_http(self):
        from streamlit.testing.v1 import AppTest
        a = AppTest.from_file(str(_APP)).run(timeout=20)
        a.selectbox[0].set_value(_SOURCE).run(timeout=20)
        a.selectbox[1].set_value(_CUSTOM).run(timeout=20)
        self.assertTrue(a.text_input)
        self.assertFalse(any(m.label == "데모 Guard 판정" for m in a.metric))
        a.text_input[0].set_value("8.25").run(timeout=20)
        self.assertFalse(any(m.label == "데모 Guard 판정" for m in a.metric))
        with patch("urllib.request.urlopen", side_effect=AssertionError("HTTP_DENIED")) as http:
            a.button[0].click().run(timeout=20)
        http.assert_not_called()
        self.assertFalse(a.exception, [str(e.message) for e in a.exception])
        self.assertTrue(any(m.label == "데모 Guard 판정" and m.value == "REJECT" for m in a.metric))
        self.assertTrue(any("가상 8.25% 성장 주장" in x.value for x in a.error))

    def test_invalid_change_clears_stale_guard_and_fails_closed(self):
        from streamlit.testing.v1 import AppTest
        a = AppTest.from_file(str(_APP)).run(timeout=20)
        a.selectbox[0].set_value(_SOURCE).run(timeout=20)
        a.selectbox[1].set_value(_CUSTOM).run(timeout=20)
        a.button[0].click().run(timeout=20)
        self.assertTrue(any(m.label == "데모 Guard 판정" for m in a.metric))
        a.text_input[0].set_value("NaN").run(timeout=20)
        self.assertFalse(any(m.label == "데모 Guard 판정" for m in a.metric))
        a.button[0].click().run(timeout=20)
        self.assertFalse(a.exception, [str(e.message) for e in a.exception])
        self.assertTrue(any("입력값 또는 수동 근거" in x.value for x in a.error))
        self.assertFalse(any(m.label == "데모 Guard 판정" for m in a.metric))


if __name__ == "__main__":
    unittest.main()
