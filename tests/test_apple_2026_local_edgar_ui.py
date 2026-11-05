"""P237 native Apple local SEC intake is default-off and not source auth."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch


class Local2026SECFileAppTests(unittest.TestCase):
    def test_default_no_file_processing_or_network(self):
        from streamlit.testing.v1 import AppTest
        mode="KUODRA · Apple FY2026 실제 공시 수치 검산 (원본 미인증)"
        app=Path(__file__).resolve().parents[1]/"streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True), patch(
                   "proofinvest.apple_2026_local_edgar_replay.verify_operator_apple_2026_edgar_html",
                   side_effect=AssertionError("NO_AUTO_FILE_READ")) as inspect:
            at=AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(mode).run(timeout=30)
            self.assertFalse(at.exception,[str(x.message) for x in at.exception])
            self.assertTrue(any("보유 중인 Apple FY2026 SEC 원문" in x.label
                                for x in at.get("expander")))
            self.assertTrue(any(x.key=="p237_local_read_consent"
                                and not x.value for x in at.checkbox))
            btn=next(x for x in at.button
                     if x.key=="p237_run_local_sec_check")
            self.assertTrue(btn.disabled)
            self.assertFalse(any("로컬 HTML의 SEC 공개 색인" in x.value
                                 for x in at.info))
            inspect.assert_not_called()
