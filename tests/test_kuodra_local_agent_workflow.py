"""Real in-process local question -> ML / SEC -> Guard review, fictional only."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_local_agent_workflow import (
    plan_local_question, render_local_question_html, run_owner_local_question,
)
from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from proofinvest.kuodra_synthetic_demo import _csv, _table_rows
from proofinvest.guard_audit import GuardAuditStore

OWNER = VerifiedPrincipal("fictionalOwner", "fictionalFund", ("owner",), True)
ANALYST = VerifiedPrincipal("fictionalAnalyst", "fictionalFund", ("analyst",), True)
OUTSIDER = VerifiedPrincipal("otherAnalyst", "otherFund", ("analyst",), True)
QUESTION = "SEC 공시와 다변수 ML을 검토해줘"


class LocalQuestionToolWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kuodra-local-question-")
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "audit.sqlite"
        self.vault = OwnerLocalGateway("fictionalFund")
        factor = [(entity, "feature", observed, ready, value, unit)
                  for entity, _, observed, ready, value, unit
                  in _table_rows(metric="factor")]
        target = [(entity, "target", observed, ready, value, unit)
                  for entity, _, observed, ready, value, unit
                  in _table_rows(metric="outcome")]
        self.vault.ingest_csv(OWNER, raw=_csv(factor + target),
            dataset_id="secretPrivate", source_id="fictionalMLSource",
            access_level="PRIVATE")
        submissions = synthetic_submissions()
        companyfacts = json.dumps(synthetic_companyfacts(), sort_keys=True).encode()
        self.sec_bytes = dict(submissions_json=submissions,
                              companyfacts_json=companyfacts,
                              original_filing=SYNTHETIC_HTML)
        self.sec_options = dict(
            cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
            as_of=AS_OF, collected_at=COLLECTED_AT,
            current_end="2025-09-30", prior_end="2024-09-30",
            needle=PHRASE, audit_db_path=self.db, run_id="fictionalOne",
            claimed_growth_pct="100.00",
            expected_source_sha256={
                "submissions": sha256(submissions).hexdigest(),
                "companyfacts": sha256(companyfacts).hexdigest(),
                "original_filing": sha256(SYNTHETIC_HTML).hexdigest(),
            },
        )
        self.ml_options = dict(private_dataset_id="secretPrivate",
            target_metric="target", feature_metrics=("feature",),
            ml_as_of="2026-01-01T00:00:00Z")

    def call(self, question=QUESTION, *, principal=ANALYST,
             ml=True, sec=True, consent=True, **changes):
        params = dict(
            vault=self.vault, principal=principal,
            sec_bytes=self.sec_bytes if sec else None,
            sec_options=self.sec_options if sec else None,
            consent_local_sec_audit=consent if sec else False,
        )
        if ml:
            params.update(self.ml_options)
        params.update(changes)
        return run_owner_local_question(question, **params)

    def test_planner_routes_explicit_modes_without_execution(self):
        self.assertEqual(plan_local_question(QUESTION)["mode"], "SEC_ML")
        self.assertEqual(plan_local_question("SEC 공시 원문 검토")["mode"], "SEC_ONLY")
        self.assertEqual(plan_local_question("비공개 다변수 ML 검토")["mode"], "ML_ONLY")
        self.assertEqual(plan_local_question("그냥 해줘")["status"], "NEEDS_CLARIFICATION")
        self.assertEqual(plan_local_question("공시 검토하고 매수 주문")["status"], "BLOCKED")
        self.assertEqual(plan_local_question("https://attacker.example SEC")["status"], "BLOCKED")
        self.assertFalse(self.db.exists())

    def test_joint_real_tools_hold_audit_and_redacted_report(self):
        originals = {k: sha256(v).hexdigest() for k, v in self.sec_bytes.items()}
        result = self.call()
        self.assertEqual(result["status"], "LOCAL_HUMAN_REVIEW_REQUIRED", result)
        self.assertEqual(result["mode"], "SEC_ML")
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["tool_calls"], 2)
        self.assertEqual(result["review"]["ml"]["summary"]["status"],
                         "EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertIn("time_trend_warning", result["review"]["ml"]["summary"])
        self.assertEqual(result["cross_source_entity_link"],
                         "NOT_ESTABLISHED_DO_NOT_JOIN_OR_COMPARE_ISSUERS")
        self.assertTrue(result["audit_written"])
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertEqual({k: sha256(v).hexdigest()
                          for k, v in self.sec_bytes.items()}, originals)
        self.assertFalse(result["public_export_allowed"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["institution_host_iam_verified"])
        self.assertFalse(result["production_ready"])
        self.assertEqual(result["network_requests"], 0)
        body = json.dumps(result, ensure_ascii=True)
        for secret in ("secretPrivate", "fictionalMLSource",
                       "fictitiousIssuer0", "fictionalFund", "fictionalOwner"):
            self.assertNotIn(secret, body)

    def test_joint_sec_conflict_reject_overrides_ml(self):
        self.sec_options["claimed_growth_pct"] = "300.00"
        result = self.call()
        self.assertEqual(result["status"], "LOCAL_HUMAN_REVIEW_REQUIRED", result)
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["review"]["sec"]["decision"], "REJECT")
        self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_ml_only_routes_without_sec_audit_or_consent(self):
        result = self.call("비공개 다변수 ML 검토", sec=False, consent=False)
        self.assertEqual(result["mode"], "ML_ONLY")
        self.assertEqual(result["decision"], "HOLD")
        self.assertFalse(result["audit_written"])
        self.assertFalse(self.db.exists())
        self.assertNotIn("secretPrivate", json.dumps(result))

    def test_sec_only_routes_and_does_not_read_ml(self):
        with patch("proofinvest.kuodra_local_agent_workflow.build_owner_group_review",
                   side_effect=AssertionError("ML_UNSELECTED")) as called:
            result = self.call("SEC 공시 원문 검토", ml=False)
        called.assert_not_called()
        self.assertEqual(result["mode"], "SEC_ONLY")
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(result["review"]["numeric_status"], "calculated_unverified")
        self.assertTrue(self.db.exists())

    def test_no_audit_without_explicit_consent_or_pins(self):
        result = self.call(consent=False)
        self.assertEqual(result["reason_code"],
                         "EXPLICIT_LOCAL_SEC_AUDIT_CONSENT_REQUIRED")
        self.assertFalse(self.db.exists())
        self.sec_options["expected_source_sha256"]["companyfacts"] = "a" * 64
        result = self.call()
        self.assertEqual(result["reason_code"],
                         "LOCAL_SOURCE_ACCESS_OR_TOOL_REVIEW_FAILED")
        self.assertFalse(self.db.exists())

    def test_unauthorized_identity_denied_before_tools(self):
        with patch("proofinvest.kuodra_local_agent_workflow.review_local_sec_with_guard",
                   side_effect=AssertionError("UNAUTHORIZED_SEC")) as sec:
            with patch("proofinvest.kuodra_local_agent_workflow.build_owner_group_review",
                       side_effect=AssertionError("UNAUTHORIZED_ML")) as ml:
                result = self.call(principal=OUTSIDER)
        self.assertEqual(result["status"], "BLOCKED")
        sec.assert_not_called()
        ml.assert_not_called()
        self.assertFalse(self.db.exists())

    def test_unselected_sec_tool_input_denied(self):
        result = self.call("비공개 다변수 ML 검토")
        self.assertEqual(result["reason_code"], "UNSELECTED_SEC_TOOL_INPUT_DENIED")
        self.assertFalse(self.db.exists())

    def test_illegal_user_request_does_not_call_tools(self):
        with patch("proofinvest.kuodra_local_agent_workflow.review_local_sec_with_guard",
                   side_effect=AssertionError("NO_SEC")) as sec:
            with patch("proofinvest.kuodra_local_agent_workflow.build_owner_group_review",
                       side_effect=AssertionError("NO_ML")) as ml:
                result = self.call("SEC 공시 확인 후 자동매매 실행")
        self.assertEqual(result["reason_code"], "UNAUTHORIZED_ACTION_INTENT")
        sec.assert_not_called()
        ml.assert_not_called()
        self.assertFalse(self.db.exists())

    def test_unreviewed_extra_options_cannot_enable_actions(self):
        self.sec_options["action"] = "REQUEST_EXCEPTION"
        result = self.call()
        self.assertEqual(result["reason_code"], "LOCAL_SEC_PINS_OR_AUDIT_PATH_INVALID")
        self.assertFalse(self.db.exists())

    def test_ml_validation_failure_precedes_any_sec_audit(self):
        self.ml_options["target_metric"] = "feature"
        result = self.call()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(self.db.exists())

    def test_html_receipt_and_no_active_content(self):
        result = self.call()
        html = render_local_question_html(result)
        self.assertIn("default-src 'none'", html)
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("fictitiousIssuer0", html)
        result["decision"] = "REJECT"
        with self.assertRaisesRegex(ValueError, "LOCAL_AGENT_HTML_RECEIPT_INVALID"):
            render_local_question_html(result)

    def test_mock_socket_no_external_calls(self):
        with patch.object(socket.socket, "connect",
                          side_effect=AssertionError("EXTERNAL_NETWORK")) as connect:
            result = self.call()
            connect.assert_not_called()
        self.assertEqual(result["decision"], "HOLD")
        self.assertFalse(result["llm_agent_executed"])


if __name__ == "__main__":
    unittest.main()
