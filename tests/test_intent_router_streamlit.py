"""Headless Streamlit AppTest for bounded question-to-tool selection."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
MODE = "질문별 로컬 도구 선택 — 규칙 기반 시연"


class IntentRouterStreamlitTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="kic-router-ui-")
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        p = patch.dict(os.environ, {"HOME": str(self.home)})
        p.start()
        self.addCleanup(p.stop)

    def screen(self):
        at = AppTest.from_file(str(APP)).run(timeout=15)
        at.selectbox[0].set_value(MODE).run(timeout=15)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        return at

    def test_router_requires_explicit_click_and_rejects_conflicting_growth(self):
        at = self.screen()
        self.assertTrue(any("RULE_BASED_OFFLINE_NOT_LLM" in x.value for x in at.warning))
        self.assertFalse(any(m.label == "Guard 판정 (모의)" for m in at.metric))
        at.button(key="intent_router_run").click().run(timeout=15)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any(m.label == "선택한 경로" and m.value == "GROWTH_CHECK"
                            for m in at.metric))
        self.assertTrue(any(m.label == "Guard 판정 (모의)" and m.value == "REJECT"
                            for m in at.metric))
        self.assertTrue(any("GROWTH_CLAIM_CONFLICT" in x.value for x in at.error))
        self.assertFalse((self.home / ".proofinvest-guard").exists())

    def test_router_filing_and_risk_paths_are_fail_closed(self):
        for question, expected in (
            ("Apple 2025 공시 근거", "SOURCE_REVIEW"),
            ("Apple 2025 부채비율", "RISK_CHECK"),
        ):
            with self.subTest(question=question):
                at = self.screen()
                at.text_area(key="intent_router_question").set_value(question)
                at.button(key="intent_router_run").click().run(timeout=15)
                self.assertFalse(at.exception, [str(x.message) for x in at.exception])
                self.assertTrue(any(m.label == "선택한 경로" and m.value == expected
                                    for m in at.metric))
                self.assertFalse(any(m.value == "APPROVE" for m in at.metric))
        self.assertFalse((self.home / ".proofinvest-guard").exists())

    def test_ambiguous_intent_asks_user_instead_of_running_tools(self):
        at = self.screen()
        at.text_area(key="intent_router_question").set_value(
            "Apple 성장률과 부채위험 모두 확인"
        )
        at.button(key="intent_router_run").click().run(timeout=15)
        self.assertFalse(at.exception)
        self.assertTrue(any("무엇을 확인할까요" in w.value for w in at.warning))
        self.assertFalse(any(m.label == "선택한 경로" for m in at.metric))


if __name__ == "__main__":
    unittest.main()
