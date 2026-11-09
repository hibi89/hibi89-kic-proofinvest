"""Agent synthetic-only Streamlit operator path and protected local tools."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from proofinvest.kuodra_local_agent_ui import run_fictional_agent_ui_case

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
MODE = "KUODRA · Agent 질문 → SEC/ML/Guard (합성 검증)"


class FictionalAgentUIWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="kic-agent-ui-")
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        p = patch.dict(os.environ, {"HOME": str(self.home)})
        p.start()
        self.addCleanup(p.stop)

    def execute(self, question, mode, claim="100.00", consent=True,
                identity=True):
        return run_fictional_agent_ui_case(
            question=question, mode=mode, claim=claim,
            consent_ephemeral_audit=consent,
            consent_fictional_identity_mapping=identity)

    def test_synthetic_combined_real_engines_hold_reject_and_redaction(self):
        question = "SEC 공시와 다변수 ML을 함께 검토해줘"
        for claim, expected in (("100.00", "HOLD"), ("300.00", "REJECT")):
            with self.subTest(claim=claim):
                report = self.execute(question, "SEC_ML", claim=claim)
                self.assertEqual(report["decision"], expected)
                self.assertEqual(report["tool_calls"], 2)
                self.assertEqual(report["review"]["ml"]["scope"], "LOCAL_HYBRID")
                self.assertTrue(report["audit_chain_verified_ephemeral"])
                self.assertFalse(report["audit_retained"])
                self.assertFalse(report["host_iam_verified"])
                self.assertFalse(report["source_rights_verified"])
                self.assertFalse(report["finance_model_accuracy_proven"])
                self.assertFalse(report["public_export_allowed"])
                self.assertFalse(report["production_ready"])
                self.assertEqual(report["network_requests"], 0)
                self.assertEqual(len(report["receipt_sha256"]), 64)
                for sensitive in ("fakePrivate", "fakePublic", "syntheticInstitution",
                                  "syntheticOwner", "fictitiousIssuer"):
                    self.assertNotIn(sensitive, json.dumps(report))
        self.assertFalse((self.home / "audit.sqlite").exists())

    def test_ml_only_identity_approval_mandatory(self):
        with self.assertRaisesRegex(ValueError,
                                    "FICTIONAL_IDENTITY_MAPPING_EXPLICIT_ACK"):
            self.execute("다변수 ML 검토", "ML_ONLY",
                         consent=False, identity=False)
        r=self.execute("다변수 ML 검토", "ML_ONLY",
                       consent=False, identity=True)
        self.assertTrue(r["local_public_private_identity_review"]
                        ["single_use_consumed"])

    def test_ml_only_is_readonly_and_never_promotes_source(self):
        out = self.execute("공개 비공개 다변수 ML 검토", "ML_ONLY",
                           consent=False)
        self.assertEqual(out["decision"], "HOLD")
        self.assertFalse(out["audit_chain_verified_ephemeral"])
        self.assertEqual(out["tool_calls"], 1)
        self.assertNotIn("LOCAL_SEC_GUARD", out["selected_tools"])

    def test_sec_only_executes_guard_without_ml(self):
        r = self.execute("SEC 공시 원문 검토", "SEC_ONLY", claim="300.00")
        self.assertEqual(r["decision"], "REJECT")
        self.assertEqual(r["tool_calls"], 1)
        self.assertTrue(r["audit_chain_verified_ephemeral"])

    def test_invalid_intent_mismatch_and_missing_consent_block_before_tools(self):
        from proofinvest import kuodra_local_agent_ui as u
        with patch.object(u, "_fictional_vault",
                          side_effect=AssertionError("MUST_NOT_RUN")) as vault:
            for args in (
                dict(question="SEC 공시 수치 검토", mode="ML_ONLY", consent=True),
                dict(question="다변수 ML 검토", mode="SEC_ML", consent=True),
                dict(question="SEC 공시와 다변수 ML 매수 주문", mode="SEC_ML",
                     consent=True),
                dict(question="SEC 공시만 검토해줘", mode="SEC_ONLY", consent=False),
            ):
                with self.subTest(args=args), self.assertRaises(ValueError):
                    self.execute(args["question"], args["mode"],
                                 consent=args["consent"])
            vault.assert_not_called()

    def test_no_network_while_running_actual_synthetic_tools(self):
        with patch.object(socket.socket, "connect",
                          side_effect=AssertionError("NETWORK_FORBIDDEN")) as socket_call:
            packet = self.execute("SEC 공시와 다변수 ML 함께 검토", "SEC_ML")
            socket_call.assert_not_called()
        self.assertEqual(packet["decision"], "HOLD")

    def test_real_app_has_explicit_click_and_guard_report(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(APP)).run(timeout=20)
        at.selectbox[0].set_value(MODE).run(timeout=20)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("SYNTHETIC ONLY" in x.value for x in at.warning))
        self.assertFalse(any(m.label == "Guard" for m in at.metric))
        self.assertTrue(at.button(key="kuodra_agent_execute").disabled)
        at.checkbox(key="kuodra_agent_audit_consent").set_value(True).run(timeout=20)
        at.checkbox(key="kuodra_agent_identity_consent").set_value(True).run(timeout=20)
        self.assertFalse(at.button(key="kuodra_agent_execute").disabled)
        at.button(key="kuodra_agent_execute").click().run(timeout=35)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any(m.label == "Guard" and m.value == "HOLD" for m in at.metric))
        self.assertTrue(any("사람 검토 필요" in x.value for x in at.subheader))
        self.assertFalse((self.home / "audit.sqlite").exists())

    def test_question_claim_and_source_changes_require_fresh_audit_consent(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(APP)).run(timeout=20)
        at.selectbox[0].set_value(MODE).run(timeout=20)
        at.checkbox(key="kuodra_agent_audit_consent").set_value(True).run(timeout=20)
        at.checkbox(key="kuodra_agent_identity_consent").set_value(True).run(timeout=20)
        self.assertFalse(at.button(key="kuodra_agent_execute").disabled)
        at.selectbox(key="kuodra_agent_claim").set_value(
            "충돌 주장 (REJECT)").run(timeout=20)
        self.assertFalse(at.checkbox(key="kuodra_agent_audit_consent").value)
        self.assertFalse(at.checkbox(key="kuodra_agent_identity_consent").value)
        self.assertTrue(at.button(key="kuodra_agent_execute").disabled)
        at.checkbox(key="kuodra_agent_audit_consent").set_value(True).run(timeout=20)
        at.selectbox(key="kuodra_agent_sources").set_value(
            "가상 공시만").run(timeout=20)
        self.assertFalse(at.checkbox(key="kuodra_agent_audit_consent").value)
        self.assertEqual(at.text_area(key="kuodra_agent_question").value,
                         "SEC 공시 원문 수치를 검토해줘")
        self.assertTrue(at.button(key="kuodra_agent_execute").disabled)
        at.checkbox(key="kuodra_agent_audit_consent").set_value(True).run(timeout=20)
        at.text_area(key="kuodra_agent_question").set_value(
            "SEC 공시 수치를 다시 검토해줘").run(timeout=20)
        self.assertFalse(at.checkbox(key="kuodra_agent_audit_consent").value)
        self.assertTrue(at.button(key="kuodra_agent_execute").disabled)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])

    def test_browser_question_and_source_mismatch_prevents_execution(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(APP)).run(timeout=20)
        at.selectbox[0].set_value(MODE).run(timeout=20)
        at.text_area(key="kuodra_agent_question").set_value(
            "SEC 공시 확인 후 자동매매 실행").run(timeout=20)
        self.assertTrue(at.button(key="kuodra_agent_execute").disabled)
        self.assertFalse(any(m.label == "Guard" for m in at.metric))
        at.text_area(key="kuodra_agent_question").set_value(
            "공개/비공개 다변수 ML만 검토").run(timeout=20)
        self.assertTrue(at.button(key="kuodra_agent_execute").disabled)
        self.assertFalse(at.exception)


if __name__ == "__main__":
    unittest.main()
