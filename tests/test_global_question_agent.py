"""P264: real issuer-backed user question routing and guarded response."""
from __future__ import annotations
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from proofinvest.global_question_agent import (
    answer_global_question, preflight_global_question,
    verify_global_question_answer,
)


class GlobalQuestionTests(unittest.TestCase):
    def test_nvda_inventory_query_uses_actual_source_review_and_guard(self):
        question = "엔비디아 NVDA 재고가 매출보다 빠르게 증가했나요?"
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("EXTERNAL_HTTP_FORBIDDEN")) as blocked:
            r = answer_global_question(question)
            self.assertTrue(verify_global_question_answer(r,question))
        blocked.assert_not_called()
        self.assertEqual(r["status"], "QUESTION_SOURCE_BOUND_LOCAL_REVIEW_HOLD")
        self.assertEqual(r["ticker"], "NVDA")
        self.assertEqual(r["intent"], "WORKING_CAPITAL")
        self.assertIn("46.86pp", r["answer"])
        self.assertIn("1.30pp", r["answer"])
        self.assertIn("Guard HOLD", r["answer"])
        self.assertEqual(r["tool_calls"], 1)
        self.assertEqual(r["local_model_calls"], 0)
        self.assertFalse(r["source_rights_verified"])
        self.assertFalse(r["ai_agent_executed"])
        self.assertFalse(r["trade_executed"])
        self.assertEqual(len(r["source_links"]),1)
        self.assertEqual(len(r["source_links"][0]["sha256"]),64)

    def test_dell_cashflow_question_and_market_withholding(self):
        q = "DELL 영업현금흐름과 순이익은 어떤가요?"
        r=answer_global_question(q)
        self.assertEqual(r["intent"], "CASHFLOW")
        self.assertIn("1.8843배",r["answer"])
        self.assertTrue(verify_global_question_answer(r,q))
        market=answer_global_question("NVDA Nasdaq 주가 거품인가요?")
        self.assertEqual(market["intent"],"MARKET")
        self.assertIn("UNAVAILABLE",market["answer"])
        self.assertNotIn("QQQ 대체",market["answer"])
        self.assertTrue(verify_global_question_answer(
            market,"NVDA Nasdaq 주가 거품인가요?"))

    def test_peer_references_and_dell_unavailable(self):
        q="NVIDIA 경쟁사 매출 성장률 비교"
        nvda=answer_global_question(q)
        self.assertEqual(nvda["intent"],"PEERS")
        self.assertIn("AMD 34.34%",nvda["answer"])
        self.assertIn("INTC -0.47%",nvda["answer"])
        self.assertEqual(len(nvda["source_links"]),3)
        self.assertFalse(nvda["source_links"][1]["rights_verified"])
        self.assertTrue(verify_global_question_answer(nvda,q))
        dell=answer_global_question("DELL 경쟁사 비교해줘")
        self.assertEqual(dell["intent"],"PEERS")
        self.assertIn("제공할 수 없습니다",dell["answer"])
        self.assertEqual(len(dell["source_links"]),1)

    def test_guard_source_and_income_are_not_investment_advice(self):
        for q,intent in (
            ("델 매수해도 되나요?","GUARD"),
            ("NVIDIA 원문 출처 확인","SOURCE"),
            ("NVDA 매출 증가율","REVENUE"),
        ):
            with self.subTest(q=q):
                r=answer_global_question(q)
                self.assertEqual(r["intent"],intent)
                self.assertIn("Guard HOLD",r["answer"])
                self.assertTrue(verify_global_question_answer(r,q))
                self.assertFalse(r["full_abc_complete"])

    def test_ambiguous_unsupported_and_secret_text_never_use_tools(self):
        cases=[
            "", "BUY", "AAPL 재고 증가율", "NVDA DELL 재고 증가율",
            "NVDA 2024년 성장률", "NVDA 주가 QQQ",
            "엔비디아 문의 https://example.com",
            "NVIDIA admin@example.com 재고",
            "NVDA\n재고", "NVIDIA 무슨 상관",
        ]
        with patch("proofinvest.global_question_agent.build_marketless_global_review",
                   side_effect=AssertionError("PRECHECK_MUST_BLOCK")) as source:
            for q in cases:
                with self.subTest(q=q):
                    r=answer_global_question(q)
                    self.assertEqual(r["status"],"BLOCKED",r)
                    self.assertEqual(r["tool_calls"],0)
            source.assert_not_called()

    def test_opt_in_model_denied_before_network(self):
        with patch("proofinvest.global_question_agent._call_loopback",
                   side_effect=AssertionError("LOCAL_MODEL_FORBIDDEN")) as net:
            q="NVDA 재고 증가율은?"
            blocked=answer_global_question(q,use_local_model=True)
            self.assertEqual(blocked["reason_code"],
                             "TWO_LOCAL_MODEL_CONSENTS_REQUIRED")
            self.assertEqual(blocked["tool_calls"],0)
            net.assert_not_called()

    def test_valid_local_protocol_but_no_claim_of_full_ai_agent(self):
        q="NVDA 재고 증가율은?"
        response=json.dumps({
            "done":True,"model":"qwen2.5:1.5b-instruct","eval_count":6,
            "response":json.dumps({
                "issuer":"NVDA","intent":"WORKING_CAPITAL",
                "decision":"HUMAN_REVIEW_ONLY"
            }),
        }).encode()
        with patch("proofinvest.global_question_agent._call_loopback",
                   return_value=response) as mocked:
            r=answer_global_question(q,use_local_model=True,
                consent_local_model=True,consent_question_text=True)
        mocked.assert_called_once()
        self.assertEqual(r["status"],"QUESTION_SOURCE_BOUND_LOCAL_REVIEW_HOLD",r)
        self.assertEqual(r["local_model_calls"],1)
        self.assertTrue(r["local_model_protocol_verified"])
        self.assertFalse(r["ai_agent_executed"])
        self.assertTrue(verify_global_question_answer(r,q))

    def test_invalid_model_suggestion_cannot_call_financial_tools(self):
        q="NVDA 재고 증가율은?"
        for out in (
            {"issuer":"DELL","intent":"WORKING_CAPITAL",
             "decision":"HUMAN_REVIEW_ONLY"},
            {"issuer":"NVDA","intent":"MARKET","decision":"HUMAN_REVIEW_ONLY"},
            {"issuer":"NVDA","intent":"WORKING_CAPITAL","decision":"APPROVE"},
        ):
            with self.subTest(out=out):
                raw=json.dumps({"done":True,"model":"qwen2.5:1.5b-instruct",
                       "eval_count":4,"response":json.dumps(out)}).encode()
                with patch("proofinvest.global_question_agent._call_loopback",
                           return_value=raw):
                    with patch("proofinvest.global_question_agent.build_marketless_global_review",
                               side_effect=AssertionError("NO_TOOL_AFTER_BAD_PLAN")) as engine:
                        r=answer_global_question(q,use_local_model=True,
                          consent_local_model=True,consent_question_text=True)
                        self.assertEqual(r["status"],"BLOCKED",r)
                        self.assertEqual(r["reason_code"],"LOCAL_MODEL_PLAN_REJECTED")
                        engine.assert_not_called()


    def test_model_makes_actual_allowed_multi_intent_choice_not_rule_echo(self):
        q="For NVIDIA check inventory and cash flow, but answer the cash flow first."
        route=preflight_global_question(q)
        self.assertEqual(route["status"],"READY")
        self.assertEqual(route["intent"],"WORKING_CAPITAL")
        self.assertEqual(route["candidate_intents"],
                         ["WORKING_CAPITAL","CASHFLOW"])
        raw=json.dumps({
            "done":True, "model":"qwen2.5:1.5b-instruct", "eval_count":5,
            "response":json.dumps({
                "issuer":"NVDA","intent":"CASHFLOW",
                "decision":"HUMAN_REVIEW_ONLY"
            })
        }).encode()
        with patch("proofinvest.global_question_agent._call_loopback",
                   return_value=raw) as local:
            result=answer_global_question(q,use_local_model=True,
                     consent_local_model=True,consent_question_text=True)
        local.assert_called_once()
        body=json.loads(local.call_args.args[0])
        self.assertEqual(body["format"]["properties"]["intent"]["enum"],
                         ["WORKING_CAPITAL","CASHFLOW"])
        self.assertEqual(body["format"]["properties"]["issuer"]["enum"],
                         ["NVDA"])
        self.assertNotIn("65.47",body["prompt"])
        self.assertNotIn("d07c1e",body["prompt"])
        self.assertEqual(result["status"],"QUESTION_SOURCE_BOUND_LOCAL_REVIEW_HOLD",result)
        self.assertEqual(result["intent"],"CASHFLOW")
        self.assertIn("0.8555배",result["answer"])
        self.assertEqual(result["local_model_calls"],1)
        self.assertTrue(verify_global_question_answer(result,q))
        forged=deepcopy(result)
        forged["intent"]="SOURCE"
        self.assertFalse(verify_global_question_answer(forged,q))
        forged=deepcopy(result)
        forged["answer"]="사세요"
        self.assertFalse(verify_global_question_answer(forged,q))

    def test_dynamic_tool_choice_still_blocks_unlisted_intent(self):
        q="For NVIDIA check inventory and cash flow, but answer the cash flow first."
        raw=json.dumps({
            "done":True,"model":"qwen2.5:1.5b-instruct","eval_count":4,
            "response":json.dumps({
                "issuer":"NVDA","intent":"MARKET",
                "decision":"HUMAN_REVIEW_ONLY"
            }),
        }).encode()
        with patch("proofinvest.global_question_agent._call_loopback",
                   return_value=raw):
            with patch("proofinvest.global_question_agent.build_marketless_global_review",
                       side_effect=AssertionError("NO_TOOL")) as tools:
                result=answer_global_question(q,use_local_model=True,
                    consent_local_model=True,consent_question_text=True)
                self.assertEqual(result["status"],"BLOCKED")
                self.assertEqual(result["reason_code"],"LOCAL_MODEL_PLAN_REJECTED")
                tools.assert_not_called()

    def test_forged_source_or_words_fails_replay(self):
        q="NVIDIA 경쟁사 비교"
        r=answer_global_question(q)
        for key,value in (
            ("answer","사세요"),("intent","GUARD"),("source_links",[]),
            ("source_rights_verified",True),("tool_calls",42),
            ("question_sha256","0"*64),
        ):
            tampered=deepcopy(r)
            tampered[key]=value
            self.assertFalse(verify_global_question_answer(tampered,q),key)


if __name__ == "__main__":
    unittest.main()
