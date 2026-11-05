"""P235 Streamlit default-off source-card model, no HTTP without consent."""
from pathlib import Path
import unittest
from unittest.mock import patch


class SourceCardModelAppTests(unittest.TestCase):
    def test_live_issuer_page_starts_with_zero_model_requests(self):
        from streamlit.testing.v1 import AppTest
        app=Path(__file__).resolve().parents[1]/"streamlit_app.py"
        mode="KUODRA · Apple FY2026 실제 공시 수치 검산 (원본 미인증)"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True),patch(
            "proofinvest.apple_qwen_public_brief._call_loopback",
            side_effect=AssertionError("NO_AUTO_HTTP")
        ) as net:
            at=AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(mode).run(timeout=30)
            self.assertFalse(at.exception,[str(x.message) for x in at.exception])
            self.assertTrue(any(x.key=="p235_local_model_confirmed"
                                and not x.value for x in at.checkbox))
            self.assertTrue(any(x.key=="p235_public_summary_consent"
                                and not x.value for x in at.checkbox))
            b=next(x for x in at.button if x.key=="p235_model_brief_run")
            self.assertTrue(b.disabled)
            net.assert_not_called()
