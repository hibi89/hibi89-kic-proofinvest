"""P233 AppTest: no automatic real-model call on Apple official-public tab."""
import unittest
from pathlib import Path
from unittest.mock import patch


class QwenLocalNativeUITests(unittest.TestCase):
    def test_model_default_disabled_and_no_auto_http(self):
        from streamlit.testing.v1 import AppTest
        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        mode = "KUODRA · Apple FY2026 실제 공시 수치 검산 (원본 미인증)"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True), patch(
                   "proofinvest.apple_qwen_public_claim._call_loopback",
                   side_effect=AssertionError("DO_NOT_CALL_LOCAL_MODEL")) as call:
            at = AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(mode).run(timeout=30)
            self.assertFalse(at.exception,
                             [str(x.message) for x in at.exception])
            self.assertTrue(any(x.key == "p233_qwen_local_consent"
                                for x in at.checkbox))
            self.assertTrue(any(x.key == "p233_qwen_public_numeric_consent"
                                for x in at.checkbox))
            button = next(x for x in at.button
                          if x.key == "p233_qwen_fact_execute")
            self.assertTrue(button.disabled)
            self.assertFalse(any("로컬 Qwen 실제 응답과 독립"
                                 in x.message for x in at.success))
            call.assert_not_called()
