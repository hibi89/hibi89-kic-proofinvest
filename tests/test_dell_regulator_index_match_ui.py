"""P204 native Streamlit regulator/issuer original reconciliation display."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_MODE = "KUODRA · Apple FY2026 실제 공시 수치 검산 (원본 미인증)"


class SecIndexIssuerNativeUITests(unittest.TestCase):
    def test_sec_index_filing_identity_and_explicit_non_auth_are_visible(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(_APP)).run(timeout=25)
        at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("SEC 제출 색인" in x.value for x in at.subheader))
        self.assertTrue(any("원본 동일성은 인증되지" in x.value for x in at.warning))
        self.assertFalse(at.error)

    def test_forged_regulator_result_never_displays_trusted_header(self):
        from streamlit.testing.v1 import AppTest
        from proofinvest import dell_regulator_index_match as p
        at=AppTest.from_file(str(_APP)).run(timeout=25)
        with patch.object(p,"reviewed_real_dell_regulator_issuer_evidence",
                          return_value={"status":"BLOCKED"}):
            at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertTrue(any("종목·기간 대응" in x.value for x in at.error))
        self.assertFalse(any("SEC 제출 색인" in x.value for x in at.subheader))
        self.assertFalse(at.success, "A rejected SEC match must not show prior source success")
        self.assertFalse(any("Inline XBRL" in x.value for x in at.subheader))


    def test_rejected_ixbrl_cannot_emit_premature_publisher_success(self):
        from streamlit.testing.v1 import AppTest
        from proofinvest import dell_2026_ixbrl_review as p
        at = AppTest.from_file(str(_APP)).run(timeout=25)
        with patch.object(p, "review_observed_real_dell_ixbrl",
                          return_value={"status": "BLOCKED"}):
            at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertTrue(any("XBRL 회계기간" in x.value for x in at.error))
        self.assertFalse(at.success, "Rejected XBRL cannot show original-source success")
        self.assertFalse(any("SEC 제출 색인" in x.value for x in at.subheader))


if __name__ == "__main__":
    unittest.main()
