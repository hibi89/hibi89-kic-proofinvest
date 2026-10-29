"""Mock LLM proposal / deterministic tool gate: actual Streamlit AppTest.

No API keys, model calls, real SEC queries, broker orders or persistent DB.
The explicitly labeled model proposal is a fixed local test vector.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
MODE = "질문별 로컬 도구 선택 — 규칙 기반 시연"


class MockLLMProposalStreamlitTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="kic-mock-llm-ui-")
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        env = patch.dict(os.environ, {"HOME": str(self.home), "GEMINI_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)

    def screen(self):
        at = AppTest.from_file(str(APP)).run(timeout=15)
        at.selectbox[0].set_value(MODE).run(timeout=15)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("MOCK_MODEL_RESPONSE" in w.value for w in at.warning))
        return at

    def test_opening_mode_does_not_execute_model_or_tools(self):
        with patch(
            "proofinvest.intent_router.run_curated_apple_demo",
            side_effect=AssertionError("NO_EVIDENCE_LOAD_UNTIL_CLICK"),
        ), patch(
            "proofinvest.llm_proposal_gate.request_gemini_proposal",
            side_effect=AssertionError("NETWORK_NOT_ALLOWED"),
        ):
            at = self.screen()
        self.assertFalse(any(m.label == "모의 제안 게이트" for m in at.metric))
        self.assertFalse((self.home / ".proofinvest-guard").exists())

    def test_matching_model_proposal_goes_through_guard(self):
        at = self.screen()
        with patch(
            "proofinvest.llm_proposal_gate.request_gemini_proposal",
            side_effect=AssertionError("NETWORK_NOT_ALLOWED"),
        ):
            at.button(key="intent_mock_run").click().run(timeout=15)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any(m.label == "모의 제안 게이트" and m.value == "ACCEPTED"
                            for m in at.metric))
        self.assertTrue(any(m.label == "게이트가 허용한 경로"
                            and m.value == "GROWTH_CHECK" for m in at.metric))
        self.assertTrue(any(m.label == "모의 제안 경로 Guard"
                            and m.value == "REJECT" for m in at.metric))
        self.assertFalse((self.home / ".proofinvest-guard").exists())

    def test_wrong_proposal_does_not_touch_evidence_or_guard(self):
        at = self.screen()
        at.selectbox(key="intent_mock_proposal").set_value(
            "불일치 제안: SOURCE_REVIEW"
        )
        with patch(
            "proofinvest.intent_router.run_curated_apple_demo",
            side_effect=AssertionError("EVIDENCE_READ"),
        ) as load, patch(
            "proofinvest.intent_router.evaluate_sec_guard",
            side_effect=AssertionError("GUARD_CALLED"),
        ) as guard:
            at.button(key="intent_mock_run").click().run(timeout=15)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any(m.label == "모의 제안 게이트" and m.value == "BLOCKED"
                            for m in at.metric))
        self.assertFalse(any(m.label == "모의 제안 경로 Guard" for m in at.metric))
        self.assertTrue(any("로컬 도구 실행 0회" in x.value for x in at.caption))
        load.assert_not_called()
        guard.assert_not_called()

    def test_model_ask_skips_tools(self):
        at = self.screen()
        at.selectbox(key="intent_mock_proposal").set_value("모델 재질문: ASK")
        at.button(key="intent_mock_run").click().run(timeout=15)
        self.assertFalse(at.exception)
        self.assertTrue(any(m.label == "모의 제안 게이트" and m.value == "ASK"
                            for m in at.metric))
        self.assertTrue(any("재질문을 요청" in w.value for w in at.warning))
        self.assertFalse(any(m.label == "모의 제안 경로 Guard" for m in at.metric))

    def test_unauthorized_command_is_blocked(self):
        at = self.screen()
        at.selectbox(key="intent_mock_proposal").set_value("비허용 도구: run_shell")
        at.button(key="intent_mock_run").click().run(timeout=15)
        self.assertFalse(at.exception)
        self.assertTrue(any(m.label == "모의 제안 게이트" and m.value == "BLOCKED"
                            for m in at.metric))
        self.assertTrue(any("UNAUTHORIZED_MODEL_TOOL" in x.value for x in at.caption))
        self.assertFalse(any(m.label == "모의 제안 경로 Guard" for m in at.metric))


if __name__ == "__main__":
    unittest.main()
