"""P234 AppTest default off: never leaks derived public input to model."""
from pathlib import Path
import unittest
from unittest.mock import patch


class P234NativeFinancialSignalUITests(unittest.TestCase):
    def test_apple_page_default_off_no_network(self):
        from streamlit.testing.v1 import AppTest
        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        mode = "KUODRA · Apple FY2026 실제 공시 수치 검산 (원본 미인증)"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True), patch(
                   "proofinvest.apple_qwen_anomaly_screen._call_loopback",
                   side_effect=AssertionError("UNCONSENTED_LOCAL_HTTP")) as network:
            at = AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(mode).run(timeout=30)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            # P233 known-good model UI remains, but failed P234 must
            # not expose a callable production-facing control.
            self.assertTrue(any(x.key == "p233_qwen_local_consent"
                                for x in at.checkbox))
            self.assertFalse(any(x.key in (
                "p234_local_model_consent", "p234_derived_public_consent")
                for x in at.checkbox))
            self.assertFalse(any(x.key == "p234_anomaly_model_run"
                                 for x in at.button))
            self.assertFalse(any("재고·매출채권 두 신호의 실제 모델 응답"
                                 in x.value for x in at.success))
            network.assert_not_called()
