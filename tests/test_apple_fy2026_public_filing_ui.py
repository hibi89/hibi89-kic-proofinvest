"""P190 actual Streamlit AppTest: new first-party public financial view is actionable."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch


_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_MODE = "KUODRA · Apple FY2026 실제 공시 수치 검산 (원본 미인증)"


class ApplePublicFY2026AppTests(unittest.TestCase):
    def test_actual_streamlit_source_selector_displays_2026_real_decimal_signals(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(_APP)).run(timeout=20)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any(_MODE == option for option in at.selectbox[0].options))
        at.selectbox[0].set_value(_MODE).run(timeout=20)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("Apple FY2026" in t.value for t in at.title))
        self.assertTrue(any("PUBLIC TEXT TRANSCRIPTION" in w.value for w in at.warning))
        self.assertTrue(any(m.label == "매출 증가율 (산술)"
                            and m.value == "15.06%" for m in at.metric))
        self.assertTrue(any(m.label == "재고 증가율 (산술)"
                            and m.value == "154.30%" for m in at.metric))
        self.assertFalse(at.error)

    def test_untrusted_financial_verdict_hides_all_public_metrics(self):
        from streamlit.testing.v1 import AppTest
        from proofinvest import apple_fy2026_public_filing_review as review

        at = AppTest.from_file(str(_APP)).run(timeout=20)
        with patch.object(review, "review_apple_2026_public_financials",
                          return_value={"status": "BLOCKED"}):
            at.selectbox[0].set_value(_MODE).run(timeout=20)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(at.error)
        self.assertFalse(any("매출 증가율 (산술)" == m.label for m in at.metric))


if __name__ == "__main__":
    unittest.main()
