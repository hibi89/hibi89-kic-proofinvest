"""P192 real Streamlit public issuer model opt-in and no bypass on failure."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_MODE = "KUODRA · Apple FY2026 실제 공시 수치 검산 (원본 미인증)"
_BUTTON = "공개 SEC 숫자 로컬 모델 사실 대조 실행"


class ApplePublicIssuerModelUITests(unittest.TestCase):
    def launch(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(_APP)).run(timeout=20)
        return at.selectbox[0].set_value(_MODE).run(timeout=20)

    def test_public_default_does_not_offer_local_model_or_attempt_http(self):
        from proofinvest import apple_public_model_claim as model
        with patch.object(model, "_call_loopback",
                          side_effect=AssertionError("NEVER")) as net:
            at = self.launch()
        self.assertFalse(at.exception)
        self.assertFalse(any(b.label == _BUTTON for b in at.button))
        net.assert_not_called()

    def test_loopback_only_requires_both_consents_then_one_safe_click(self):
        from proofinvest import kuodra_local_workspace_ui as workspace
        from proofinvest import apple_public_model_claim as model
        fake = {
            "status": "REAL_MODEL_PUBLIC_ISSUER_FACT_INDEPENDENTLY_MATCHED",
            "actual_model_token_count_verified": True,
            "actual_model_factual_claim_verified": True,
            "publisher_original_bytes_authenticated": False,
            "full_market_ndx_peer_rights_verified": False,
            "model_free_text_displayed": False, "guard_policy_preview": "HOLD",
            "trade_executed": False,
            "approved_human_review_text": "Only a human-reviewed factual comparison.",
            "model_claim": "CFO_EXCEEDS_NET_INCOME",
            "evidence_id": "AAPL_2026_10K_ITEM8_CONSOLIDATED_STATEMENTS",
        }
        with patch.object(workspace, "local_workspace_enabled", return_value=True), \
             patch.object(model, "run_public_issuer_model", return_value=fake) as run:
            at = self.launch()
            btn = next(x for x in at.button if x.label == _BUTTON)
            self.assertTrue(btn.disabled)
            run.assert_not_called()
            for cb in at.checkbox:
                if "로컬 모델 연결에 동의" in cb.label:
                    cb.set_value(True)
                    break
            at.run(timeout=20)
            btn = next(x for x in at.button if x.label == _BUTTON)
            self.assertTrue(btn.disabled)
            run.assert_not_called()
            for cb in at.checkbox:
                if "공개 재무수치 2개" in cb.label:
                    cb.set_value(True)
                    break
            at.run(timeout=20)
            btn = next(x for x in at.button if x.label == _BUTTON)
            self.assertFalse(btn.disabled)
            btn.click().run(timeout=20)
            run.assert_called_once_with(consent=True)
            self.assertFalse(at.exception)
            self.assertTrue(any("독립 검산 일치" in x.value for x in at.success))

    def test_unverified_reply_is_not_displayed(self):
        from proofinvest import kuodra_local_workspace_ui as workspace
        from proofinvest import apple_public_model_claim as model
        with patch.object(workspace, "local_workspace_enabled", return_value=True), \
             patch.object(model, "run_public_issuer_model",
                          return_value={"status": "BLOCKED"}) as run:
            at = self.launch()
            for cb in at.checkbox:
                cb.set_value(True)
            at.run(timeout=20)
            next(x for x in at.button if x.label == _BUTTON).click().run(timeout=20)
            run.assert_called_once_with(consent=True)
            self.assertFalse(any("독립 검산 일치" in x.value for x in at.success))
            self.assertTrue(any("사실 대조 차단" in x.value for x in at.warning))


if __name__ == "__main__":
    unittest.main()
