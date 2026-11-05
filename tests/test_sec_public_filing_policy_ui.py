"""P236 native policy evidence card keeps source/legal rights separated."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch


class SecPolicyNativeUI(unittest.TestCase):
    def test_apple_public_policy_expander_is_explanatory_not_approval(self):
        from streamlit.testing.v1 import AppTest
        app=Path(__file__).resolve().parents[1]/"streamlit_app.py"
        mode="KUODRA · Apple FY2026 실제 공시 수치 검산 (원본 미인증)"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True), patch(
                   "urllib.request.urlopen",
                   side_effect=AssertionError("SEC_NO_REQUESTS")) as forbidden:
            at=AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(mode).run(timeout=30)
            self.assertFalse(at.exception,[str(x.message) for x in at.exception])
            self.assertTrue(any("SEC 공개 EDGAR 자료 재사용 정책" in x.label
                                for x in at.get("expander")))
            self.assertFalse(any("SEC 원본 HTML 바이트를 인증했습니다" in x.value
                                 for x in at.success))
            forbidden.assert_not_called()
