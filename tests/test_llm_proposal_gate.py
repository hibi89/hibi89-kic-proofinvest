"""ProofInvest LLM proposal security gate tests (all requests mocked/offline)."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from proofinvest.llm_proposal_gate import (
    ENDPOINT, PlannerGateError, evaluate_model_proposal,
    main, request_gemini_proposal,
)

GROWTH = "Apple FY2025 매출 성장률 20%"
SOURCE = "Apple 공시 원문 근거"
RISK = "Apple 부채비율 위험 진단"


class LLMSafetyGateTests(unittest.TestCase):
    def test_matched_growth_proposal_executes_only_pinned_local_code(self):
        result = evaluate_model_proposal(
            GROWTH, '{"action":"RUN","intent":"GROWTH_CHECK"}'
        )
        self.assertTrue(result["model_proposal_accepted"])
        self.assertEqual(result["selected_intent"], "GROWTH_CHECK")
        self.assertEqual(result["local_result"]["guard"]["decision"], "REJECT")
        self.assertEqual(result["local_result"]["evidence"]["growth_pct"], "6.43")
        self.assertEqual(result["reason_code"], "GROWTH_CLAIM_CONFLICT")
        self.assertEqual(result["external_tool_calls"], 0)
        self.assertFalse(result["trade_executed"])

    def test_source_and_risk_routes_are_bounded(self):
        for question, intent, status, expected_calls in (
            (SOURCE, "SOURCE_REVIEW", "needs_authentication", 1),
            (RISK, "RISK_CHECK", "needs_evidence", 1),
        ):
            with self.subTest(intent=intent):
                result = evaluate_model_proposal(
                    question, {"action": "RUN", "intent": intent}
                )
                self.assertTrue(result["model_proposal_accepted"])
                self.assertEqual(result["status"], status)
                self.assertEqual(len(result["local_result"]["tool_calls"]), expected_calls)
                self.assertFalse(result["authenticated_external_source"])

    def test_model_mismatch_cannot_pick_other_local_tool(self):
        for question, suggestion in (
            (GROWTH, "SOURCE_REVIEW"),
            (SOURCE, "RISK_CHECK"),
            ("Apple 성장률과 부채 위험", "GROWTH_CHECK"),
            ("Tesla 매출 성장률", "GROWTH_CHECK"),
            ("Apple 2024 매출 성장률", "GROWTH_CHECK"),
        ):
            with self.subTest(question=question):
                result = evaluate_model_proposal(
                    question, {"action": "RUN", "intent": suggestion}
                )
                self.assertEqual(result["status"], "blocked")
                self.assertFalse(result["model_proposal_accepted"])
                self.assertIsNone(result["local_result"])
                self.assertEqual(result["external_tool_calls"], 0)

    def test_ask_clarification_is_a_zero_tool_early_exit(self):
        result = evaluate_model_proposal(
            GROWTH, {"action": "ASK", "intent": None}
        )
        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual(result["reason_code"], "MODEL_REQUESTS_CLARIFICATION")
        self.assertIsNone(result["local_result"])

    def test_arbitrary_model_instructions_are_not_executable(self):
        bad = (
            '{"action":"RUN","intent":"run_shell"}',
            '{"action":"RUN","intent":"GROWTH_CHECK","command":"rm -rf /"}',
            '{"action":"RUN","intent":null}',
            '{"action":"ASK","intent":"GROWTH_CHECK"}',
            '{"action":"EXECUTE","intent":"GROWTH_CHECK"}',
            "not-json",
            "{" + "x" * 3000 + "}",
            "[]",
            '{"action":true,"intent":"GROWTH_CHECK"}',
            '{"action":"RUN","intent":["GROWTH_CHECK"]}',
        )
        for proposed in bad:
            with self.subTest(proposed=proposed[:40]):
                result = evaluate_model_proposal(GROWTH, proposed)
                self.assertEqual(result["status"], "blocked")
                self.assertFalse(result["model_proposal_accepted"])
                self.assertIsNone(result["local_result"])

    def test_invalid_question_never_runs_a_tool(self):
        for question in (None, "", "\nApple growth", "x"*241):
            self.assertIsNone(evaluate_model_proposal(
                question, {"action": "RUN", "intent": "GROWTH_CHECK"}
            )["local_result"])

    def test_network_requires_explicit_opt_in_even_when_key_exists(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "A" * 40}), \
             patch("urllib.request.build_opener") as opening:
            with self.assertRaisesRegex(PlannerGateError, "MODEL_NETWORK_OPT_IN_REQUIRED"):
                request_gemini_proposal(GROWTH)
            opening.assert_not_called()

    def test_missing_key_prevents_network(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}), \
             patch("urllib.request.build_opener") as opening:
            with self.assertRaisesRegex(PlannerGateError, "GEMINI_API_KEY_REQUIRED"):
                request_gemini_proposal(GROWTH, allow_network=True)
            opening.assert_not_called()

    def test_mocked_single_HTTPS_post_produces_only_proposal(self):
        reply = {
            "candidates": [{
                "finishReason": "STOP",
                "content": {"parts": [{
                    "text": '{"action":"RUN","intent":"GROWTH_CHECK"}'
                }]}
            }]
        }
        class Response:
            status = 200
            def geturl(self): return ENDPOINT
            def read(self, cap): return json.dumps(reply).encode("utf-8")
            def __enter__(self): return self
            def __exit__(self, *args): return None

        fake_opener = MagicMock()
        fake_opener.open.return_value = Response()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "A" * 40}), \
             patch("urllib.request.build_opener", return_value=fake_opener):
            proposal = request_gemini_proposal(GROWTH, allow_network=True)
        self.assertEqual(proposal, '{"action":"RUN","intent":"GROWTH_CHECK"}')
        fake_opener.open.assert_called_once()
        request = fake_opener.open.call_args.args[0]
        self.assertEqual(request.full_url, ENDPOINT)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(fake_opener.open.call_args.kwargs["timeout"], 20)
        body = json.loads(request.data)
        self.assertIn(GROWTH, body["contents"][0]["parts"][0]["text"])
        self.assertNotIn("A" * 40, json.dumps(body))
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        result = evaluate_model_proposal(GROWTH, proposal, llm_attempted=True)
        self.assertTrue(result["llm_request_attempted"])
        self.assertTrue(result["model_proposal_accepted"])

    def test_mocked_model_stop_without_valid_proposal_fails_closed(self):
        failure = {
            "candidates": [{
                "finishReason": "MAX_TOKENS",
                "content": {"parts": [{"text": "broken"}]}
            }]
        }
        class Response:
            status = 200
            def geturl(self): return ENDPOINT
            def read(self, max_bytes): return json.dumps(failure).encode()
            def __enter__(self): return self
            def __exit__(self, *args): return None
        opener = MagicMock()
        opener.open.return_value = Response()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "A" * 40}), \
             patch("urllib.request.build_opener", return_value=opener):
            with self.assertRaisesRegex(PlannerGateError, "MODEL_RESPONSE_CONTRACT_INVALID"):
                request_gemini_proposal(GROWTH, allow_network=True)

    def test_cli_refuses_network_without_flag(self):
        with patch("proofinvest.llm_proposal_gate.request_gemini_proposal") as request, \
             patch("builtins.print"):
            rc = main(["--question", GROWTH])
        self.assertEqual(rc, 2)
        # The client helper is called but MUST fail before any HTTP.
        request.assert_called_once_with(GROWTH, allow_network=False)


if __name__ == "__main__":
    unittest.main()
