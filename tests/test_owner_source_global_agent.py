"""One owner-uploaded arbitrary US SEC 4-file question-to-Guard workflow."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.owner_source_global_agent import (
    answer_owner_source_question, answer_owner_multi_question,
    verify_owner_source_answer,
)
from proofinvest.ticker_local_workflow import run_local_ticker_workflow
from proofinvest.owner_source_global_html import render_owner_source_html
from tests.test_ticker_local_report_replay import report_case
from tests.test_ticker_market_industry_bridge import scenario


def run(q="NVDA 매출 성장률 검증", ticker="NVDA", as_of="2025-10-16",
        sources=None, **extra):
    if sources is None:
        _,sources=report_case()
    return answer_owner_source_question(
        ticker=ticker,as_of=as_of,question=q,sources=sources,**extra)


class OwnerSourceGlobalTests(unittest.TestCase):
    def test_real_seven_stage_computation_with_operator_files(self):
        _,raw=report_case()
        before={k:sha256(v).hexdigest() for k,v in raw.items()}
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NETWORK_FORBIDDEN")) as net:
            out=run(sources=raw)
            self.assertTrue(verify_owner_source_answer(
                out,ticker="NVDA",as_of="2025-10-16",
                question="NVDA 매출 성장률 검증",sources=raw),out)
        net.assert_not_called()
        self.assertEqual(out["status"],
                         "LOCAL_OWNER_FILE_BACKED_QUESTION_HUMAN_REVIEW")
        self.assertEqual(out["fiscal_revenue_growth_pct"],"100.00")
        self.assertEqual(out["intent"],"REVENUE")
        self.assertIn("100.00%",out["answer"])
        self.assertEqual(out["guard_policy_preview"],"HOLD")
        self.assertEqual(out["executed_financial_tools"],7)
        self.assertEqual(len(out["tool_trace"]),7)
        self.assertTrue(all(x["accepted"] for x in out["tool_trace"]))
        self.assertEqual(out["sources_sha256"],before)
        self.assertEqual({k:sha256(v).hexdigest() for k,v in raw.items()},before)
        self.assertEqual(out["network_requests"],0)
        for flag in ("source_authenticated","source_rights_verified",
                     "external_sharing_allowed","ai_agent_executed",
                     "trade_executed","full_abc_complete"):
            self.assertIs(out[flag],False,flag)
        encoded=json.dumps(out,ensure_ascii=False)
        self.assertNotIn("<html",encoded)
        self.assertNotIn("PRIVATE_BYTES",encoded)

    def test_arbitrary_selected_us_ticker_not_hardcoded_nvda_or_dell(self):
        _,raw=report_case()
        # Synthetic test maps an alternate ticker to the fixture CIK.
        original=json.loads(raw["ticker_map"])
        for item in original.values():
            if item.get("ticker")=="NVDA":
                item["ticker"]="ZZZZ"
        switched=dict(raw,ticker_map=json.dumps(original).encode())
        q="이 기업의 매출 성장률은?"
        out=run(q,ticker="ZZZZ",sources=switched)
        self.assertEqual(out["status"],
                         "LOCAL_OWNER_FILE_BACKED_QUESTION_HUMAN_REVIEW",out)
        self.assertEqual(out["ticker"],"ZZZZ")
        self.assertEqual(out["intent"],"REVENUE")
        self.assertTrue(verify_owner_source_answer(
            out,ticker="ZZZZ",as_of="2025-10-16",
            question=q,sources=switched))
        self.assertFalse(out["source_authenticated"])

    def test_source_mismatch_unsupported_ticker_and_missing_raw_block(self):
        _,raw=report_case()
        wrong=run("AAPL 매출 성장률",ticker="AAPL",sources=raw)
        self.assertEqual(wrong["status"],"BLOCKED")
        conflicting=run("NVDA MSFT 매출 성장률",sources=raw)
        self.assertEqual(conflicting["reason_code"],
                         "CONFLICTING_TICKER_IN_QUESTION")
        changed=dict(raw,original_10k=b"not a genuine 10-K")
        result=run(sources=changed)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["executed_financial_tools"],0)
        self.assertFalse(verify_owner_source_answer(
            run(sources=raw),ticker="NVDA",as_of="2025-10-16",
            question="NVDA 매출 성장률 검증",sources=changed))
        for bad in (
            dict(raw,companyfacts=b""),
            dict(raw,submissions="json"),
            {"ticker_map":raw["ticker_map"]},
        ):
            with self.subTest(keys=list(bad)):
                with patch("proofinvest.owner_source_global_agent.run_local_ticker_workflow",
                           side_effect=AssertionError("SHOULD_NOT_RUN")):
                    r=run(sources=bad)
                    self.assertEqual(r["status"],"BLOCKED")

    def test_conflicting_issuer_question_blocks_before_seven_tools_or_model(self):
        _, raw = report_case()
        conflicting = (
            "AMZN 매출 성장률을 검증해줘",
            "GOOGL 매출 성장률을 검증해줘",
            "NVDA와 META 현금흐름을 비교해줘",
            "$PLTR 매출 성장률을 검증해줘",
            "NVDA $BRK.B 매출 성장률을 검증해줘",
        )
        with (
            patch("proofinvest.owner_source_global_agent.run_local_ticker_workflow",
                  side_effect=AssertionError("SOURCE_TOOLS_MUST_NOT_RUN")) as pipeline,
            patch("proofinvest.owner_source_global_agent._optional_model_plan",
                  side_effect=AssertionError("MODEL_MUST_NOT_RUN")) as model,
        ):
            for question in conflicting:
                with self.subTest(question=question):
                    r = run(question, sources=raw, use_local_model=True,
                            consent_local_model=True,
                            consent_question_text=True)
                    self.assertEqual(r["status"], "BLOCKED")
                    self.assertEqual(r["reason_code"],
                                     "CONFLICTING_TICKER_IN_QUESTION")
                    self.assertEqual(r["executed_financial_tools"], 0)
                    self.assertEqual(r["local_model_calls"], 0)
                    self.assertEqual(r["network_requests"], 0)
            pipeline.assert_not_called()
            model.assert_not_called()

    def test_matching_explicit_ticker_and_benchmark_do_not_block(self):
        _, raw = report_case()
        for question in ("$NVDA 매출 성장률 검증",
                         "NVDA 매출 성장률 검증",
                         "NVDA 시장 지수 I:NDX 출처 검토"):
            with self.subTest(question=question):
                outcome = run(question, sources=raw)
                self.assertEqual(
                    outcome["status"],
                    "LOCAL_OWNER_FILE_BACKED_QUESTION_HUMAN_REVIEW", outcome)
                self.assertEqual(outcome["ticker"], "NVDA")
                self.assertEqual(outcome["guard_policy_preview"], "HOLD")

    def test_multi_question_rejects_other_issuer_before_tools(self):
        _, raw = report_case()
        with patch("proofinvest.owner_source_global_agent.run_local_ticker_workflow",
                   side_effect=AssertionError("NO_SOURCE_REPLAY")) as pipeline:
            r = answer_owner_multi_question(
                ticker="NVDA", as_of="2025-10-16",
                question="AMZN 매출 성장률과 현금흐름을 검토해줘",
                sources=raw)
            self.assertEqual(r["status"], "BLOCKED")
            self.assertEqual(r["reason_code"],
                             "CONFLICTING_TICKER_IN_QUESTION")
            self.assertEqual(r["executed_financial_tools"], 0)
            pipeline.assert_not_called()

    def test_uploaded_market_and_industry_remain_unlicensed(self):
        _,raw,m,c=scenario()
        mb=json.dumps(m).encode()
        cb=json.dumps(c).encode()
        out=run("NVDA 주가 지수 검토",as_of="2026-02-01",
                sources=raw,market_json=mb,industry_json=cb)
        self.assertEqual(out["status"],
                         "LOCAL_OWNER_FILE_BACKED_QUESTION_HUMAN_REVIEW",out)
        self.assertEqual(out["engine_a_status"],"REPORTED_UNVERIFIED")
        self.assertEqual(out["engine_c_status"],
                         "OBSERVED_COMPARISON_UNVERIFIED")
        self.assertFalse(out["source_rights_verified"])
        self.assertTrue(verify_owner_source_answer(
            out,ticker="NVDA",as_of="2026-02-01",
            question="NVDA 주가 지수 검토",sources=raw,
            market_json=mb,industry_json=cb))
        self.assertFalse(verify_owner_source_answer(
            out,ticker="NVDA",as_of="2026-02-01",
            question="NVDA 주가 지수 검토",sources=raw,
            market_json=mb+b" ",industry_json=cb))

    def test_no_model_call_without_separate_consents(self):
        _,raw=report_case()
        with patch("proofinvest.owner_source_global_agent._optional_model_plan",
                   side_effect=AssertionError("NO_MODEL")) as model:
            out=run("NVDA 재고와 현금흐름 검토",sources=raw,
                    use_local_model=True)
            self.assertEqual(out["reason_code"],
                             "TWO_EXPLICIT_LOCAL_MODEL_CONSENTS_REQUIRED")
            model.assert_not_called()
        q="NVDA 재고와 현금흐름 검토"
        with patch("proofinvest.owner_source_global_agent._optional_model_plan",
                   return_value={"selected_intent":"CASHFLOW",
                                 "local_model_calls":1,
                                 "model_protocol_verified":True}) as model:
            out=run(q,sources=raw,use_local_model=True,
                    consent_local_model=True,consent_question_text=True)
        model.assert_called_once()
        self.assertEqual(out["status"],
                         "LOCAL_OWNER_FILE_BACKED_QUESTION_HUMAN_REVIEW")
        self.assertEqual(out["intent"],"CASHFLOW")
        self.assertTrue(verify_owner_source_answer(
            out,ticker="NVDA",as_of="2025-10-16",
            question=q,sources=raw))
        self.assertEqual(out["local_model_calls"],1)
        self.assertFalse(out["ai_agent_executed"])

    def test_invalid_filing_never_calls_optional_local_model_or_financial_tools(self):
        _, raw = report_case()
        from tests.test_ticker_research_intake import amended_submissions
        bad_facts = json.loads(raw["companyfacts"])
        bad_facts["cik"] = 320193
        cases = (
            ("COMPANYFACTS_ISSUER_MISMATCH",
             dict(raw, companyfacts=json.dumps(bad_facts).encode()), "2025-10-16"),
            ("NEWER_10K_AMENDMENT",
             dict(raw, submissions=amended_submissions()), "2025-10-17"),
            ("MISSING_10K",
             dict(raw, submissions=b'{"cik":1045810,"filings":{"recent":{}}}'),
             "2025-10-16"),
        )
        with (
            patch("proofinvest.owner_source_global_agent._optional_model_plan",
                  side_effect=AssertionError("MODEL_MUST_NOT_RUN")) as model,
            patch("proofinvest.owner_source_global_agent.run_local_ticker_workflow",
                  side_effect=AssertionError("NO_FINANCIAL_TOOLS")) as workflow,
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("NO_HTTP")) as http,
        ):
            for label, sources, cutoff in cases:
                for multi in (False, True):
                    question = ("NVDA 매출 성장률과 현금흐름 검토" if multi
                                else "NVDA 매출 성장률 검산")
                    runner = (answer_owner_multi_question if multi
                              else answer_owner_source_question)
                    with self.subTest(reason=label, multi=multi):
                        result = runner(
                            ticker="NVDA", as_of=cutoff, question=question,
                            sources=sources, use_local_model=True,
                            consent_local_model=True, consent_question_text=True,
                        )
                        self.assertEqual(result["status"], "BLOCKED")
                        self.assertEqual(
                            result["reason_code"],
                            "LOCAL_MODEL_SOURCE_IDENTITY_NOT_VERIFIED")
                        self.assertEqual(result["local_model_calls"], 0)
                        self.assertEqual(result["executed_financial_tools"], 0)
                        self.assertEqual(result["network_requests"], 0)
            model.assert_not_called()
            workflow.assert_not_called()
            http.assert_not_called()

    def test_local_model_source_gate_rejects_forged_trust_upgrade(self):
        _, raw = report_case()
        from proofinvest import owner_source_global_agent as agent
        with (
            patch("proofinvest.ticker_local_sources.prepare_local_ticker_sources",
                  return_value={
                      "schema": "kuodra.local-sec-source-receipt.v1",
                      "status": "local_four_sources_unverified",
                      "cik": "0001045810",
                      "selected_10k_accession": "0001045810-25-000020",
                      "source_authenticated": True,
                      "source_rights_verified": False,
                      "network_requests": 0,
                      "live_sec_http_called": False,
                      "external_ai_called": False,
                  }),
            patch.object(agent, "_optional_model_plan",
                         side_effect=AssertionError("MODEL_MUST_NOT_RUN")) as model,
        ):
            result = run(
                sources=raw, use_local_model=True,
                consent_local_model=True, consent_question_text=True)
        self.assertEqual(result["reason_code"],
                         "LOCAL_MODEL_SOURCE_IDENTITY_NOT_VERIFIED")
        model.assert_not_called()

    def test_original_ixbrl_must_replay_before_local_model_for_both_modes(self):
        _, raw = report_case()
        original = raw["original_10k"]
        self.assertIn(b"</body>", original)
        foreign_dei = original.replace(
            b"</body>",
            b'<ix:nonNumeric name="dei:EntityCentralIndexKey">0000320193'
            b'</ix:nonNumeric><ix:nonNumeric name="dei:DocumentType">'
            b'10-K</ix:nonNumeric></body>',
        )
        cases = (
            ("BROKEN_HTML", dict(raw, original_10k=b"not 10-K HTML")),
            ("CONFLICTING_DEI", dict(raw, original_10k=foreign_dei)),
        )
        for label, sources in cases:
            for multi in (False, True):
                question = ("NVDA 매출 성장률과 현금흐름 검토" if multi
                            else "NVDA 매출 성장률 검산")
                runner = (answer_owner_multi_question if multi
                          else answer_owner_source_question)
                with (
                    patch("proofinvest.owner_source_global_agent._optional_model_plan",
                          side_effect=AssertionError("MODEL_MUST_NOT_RUN")) as model,
                    patch("urllib.request.urlopen",
                          side_effect=AssertionError("EXTERNAL_HTTP_FORBIDDEN")) as http,
                ):
                    with self.subTest(case=label, multi=multi):
                        result = runner(
                            ticker="NVDA", as_of="2025-10-16",
                            question=question, sources=sources,
                            use_local_model=True,
                            consent_local_model=True,
                            consent_question_text=True)
                        self.assertEqual(result["status"], "BLOCKED")
                        self.assertEqual(
                            result["reason_code"],
                            "LOCAL_MODEL_ORIGINAL_REPLAY_NOT_VERIFIED")
                        self.assertEqual(result["local_model_calls"], 0)
                        self.assertEqual(result["executed_financial_tools"], 0)
                        self.assertEqual(result["network_requests"], 0)
                        model.assert_not_called()
                        http.assert_not_called()

    def test_local_model_reuses_same_seven_stage_run_after_full_replay(self):
        _, raw = report_case()
        for multi in (False, True):
            question = ("NVDA 매출 성장률과 현금흐름 검토" if multi
                        else "NVDA 매출 성장률 검산")
            runner = (answer_owner_multi_question if multi
                      else answer_owner_source_question)
            with (
                patch("proofinvest.owner_source_global_agent.run_local_ticker_workflow",
                      wraps=run_local_ticker_workflow) as pipeline,
                patch("proofinvest.owner_source_global_agent._optional_model_plan",
                      return_value={
                          "selected_intent": "REVENUE",
                          "local_model_calls": 1,
                          "model_protocol_verified": True,
                      }) as model,
            ):
                result = runner(
                    ticker="NVDA", as_of="2025-10-16",
                    question=question, sources=raw,
                    use_local_model=True, consent_local_model=True,
                    consent_question_text=True)
            with self.subTest(multi=multi):
                self.assertEqual(result["status"],
                                 "LOCAL_OWNER_FILE_BACKED_QUESTION_HUMAN_REVIEW",
                                 result)
                self.assertEqual(result["guard_policy_preview"], "HOLD")
                self.assertEqual(result["executed_financial_tools"], 7)
                self.assertEqual(result["local_model_calls"], 1)
                pipeline.assert_called_once()
                model.assert_called_once()
                self.assertTrue(verify_owner_source_answer(
                    result, ticker="NVDA", as_of="2025-10-16",
                    question=question, sources=raw))

    def test_tampered_report_or_rights_cannot_replay(self):
        _,raw=report_case()
        q="NVDA 매출 성장률 검증"
        out=run(q,sources=raw)
        for key,v in (
            ("answer","BUY NOW"),("ticker","AAPL"),
            ("source_rights_verified",True),
            ("external_sharing_allowed",True),
            ("guard_policy_preview","APPROVE"),
            ("fiscal_revenue_growth_pct","9000.00"),
            ("executed_financial_tools",8),
            ("tool_trace",[]),
        ):
            with self.subTest(key=key):
                forged=deepcopy(out)
                forged[key]=v
                self.assertFalse(verify_owner_source_answer(
                    forged,ticker="NVDA",as_of="2025-10-16",
                    question=q,sources=raw))


    def test_multi_topic_executes_single_source_pipeline_and_two_findings(self):
        _,raw=report_case()
        q="NVDA 매출 성장률과 현금흐름을 함께 검증"
        with patch("proofinvest.owner_source_global_agent.run_local_ticker_workflow",
                   wraps=run_local_ticker_workflow) as pipeline:
            result=answer_owner_multi_question(
                ticker="NVDA",as_of="2025-10-16",question=q,sources=raw)
            self.assertEqual(pipeline.call_count,1)
        self.assertEqual(result["status"],
                         "LOCAL_OWNER_FILE_BACKED_QUESTION_HUMAN_REVIEW",result)
        self.assertEqual(result["review_mode"],"MULTI_EVIDENCE_PLAN")
        self.assertEqual(result["analysis_count"],2)
        self.assertEqual(result["intent"],"CASHFLOW")
        self.assertEqual([i["tool"] for i in result["analysis_findings"]],
                         ["CASHFLOW","REVENUE"])
        self.assertEqual(result["executed_financial_tools"],7)
        self.assertEqual(len(result["tool_trace"]),7)
        self.assertIn("100.00%",result["answer"])
        self.assertIn("UNAVAILABLE",result["answer"])
        self.assertEqual(result["answer"].count("Guard HOLD"),2)
        self.assertTrue(verify_owner_source_answer(
            result,ticker="NVDA",as_of="2025-10-16",
            question=q,sources=raw))
        for field,value in (
            ("analysis_count",3),("review_mode","SINGLE_EVIDENCE"),
            ("analysis_findings",[]),("answer","매수하세요"),
            ("source_rights_verified",True),
        ):
            with self.subTest(field=field):
                forged=deepcopy(result)
                forged[field]=value
                self.assertFalse(verify_owner_source_answer(
                    forged,ticker="NVDA",as_of="2025-10-16",
                    question=q,sources=raw))

    def test_multi_topic_block_single_topic_and_more_than_four(self):
        _,raw=report_case()
        for q in (
            "NVDA 매출 성장률 검증",
            "NVDA 매수 위험 주가 재고 현금흐름 매출 성장률 원문 비교",
        ):
            with self.subTest(q=q):
                with patch("proofinvest.owner_source_global_agent.run_local_ticker_workflow",
                           side_effect=AssertionError("PIPELINE_MUST_NOT_RUN")) as pipeline:
                    result=answer_owner_multi_question(
                        ticker="NVDA",as_of="2025-10-16",question=q,sources=raw)
                    self.assertEqual(result["status"],"BLOCKED",result)
                    pipeline.assert_not_called()

    def test_multi_local_model_first_tool_changes_order_without_bypassing_guard(self):
        _,raw=report_case()
        q="NVDA 재고와 현금흐름 및 매출 성장률을 조사"
        with patch("proofinvest.owner_source_global_agent._optional_model_plan",
                   return_value={"selected_intent":"REVENUE",
                                 "local_model_calls":1,
                                 "model_protocol_verified":True}) as model:
            r=answer_owner_multi_question(
                ticker="NVDA",as_of="2025-10-16",question=q,sources=raw,
                use_local_model=True,consent_local_model=True,
                consent_question_text=True)
        model.assert_called_once()
        self.assertEqual(r["status"],
                         "LOCAL_OWNER_FILE_BACKED_QUESTION_HUMAN_REVIEW",r)
        self.assertEqual(r["intent"],"REVENUE")
        self.assertEqual([x["tool"] for x in r["analysis_findings"]],
                         ["REVENUE","WORKING_CAPITAL","CASHFLOW"])
        self.assertEqual(r["analysis_count"],3)
        self.assertEqual(r["executed_financial_tools"],7)
        self.assertTrue(verify_owner_source_answer(
            r,ticker="NVDA",as_of="2025-10-16",question=q,sources=raw))
        self.assertFalse(r["ai_agent_executed"])
        self.assertFalse(r["trade_executed"])

    def test_multi_source_bytes_and_receipt_hash_bound_all_steps(self):
        _,raw,m,c=scenario()
        q="NVDA 시장과 경쟁사 매출 성장률을 검토"
        market=json.dumps(m).encode()
        sector=json.dumps(c).encode()
        r=answer_owner_multi_question(
            ticker="NVDA",as_of="2026-02-01",question=q,sources=raw,
            market_json=market,industry_json=sector)
        self.assertEqual(r["status"],"LOCAL_OWNER_FILE_BACKED_QUESTION_HUMAN_REVIEW",r)
        self.assertEqual(r["analysis_count"],3)
        self.assertTrue(verify_owner_source_answer(
            r,ticker="NVDA",as_of="2026-02-01",question=q,sources=raw,
            market_json=market,industry_json=sector))
        self.assertFalse(verify_owner_source_answer(
            r,ticker="NVDA",as_of="2026-02-01",question=q,sources=raw,
            market_json=market+b" ",industry_json=sector))
        self.assertFalse(verify_owner_source_answer(
            r,ticker="NVDA",as_of="2026-02-01",question=q,sources=raw,
            market_json=market,industry_json=sector+b" "))


    def test_multi_printable_html_replays_every_original_and_escapes(self):
        _,raw=report_case()
        q="NVDA 매출 성장률과 현금흐름 검산"
        r=answer_owner_multi_question(
            ticker="NVDA",as_of="2025-10-16",question=q,sources=raw)
        html=render_owner_source_html(
            r,ticker="NVDA",as_of="2025-10-16",question=q,sources=raw)
        self.assertIn(b"<!doctype html>",html.lower())
        self.assertNotIn(b"<script",html.lower())
        self.assertNotIn(b"javascript:",html.lower())
        self.assertEqual(html.count(b"<section>"),2)
        self.assertIn(b"0001045810-25-000020",html)
        self.assertNotIn(b"PRIVATE_BYTES",html)
        self.assertLess(len(html),32768)
        with self.assertRaises(ValueError):
            render_owner_source_html(
                r,ticker="NVDA",as_of="2025-10-16",question=q,
                sources=dict(raw,original_10k=raw["original_10k"]+b" "))
        forged=deepcopy(r)
        forged["guard_policy_preview"]="APPROVE"
        with self.assertRaises(ValueError):
            render_owner_source_html(
                forged,ticker="NVDA",as_of="2025-10-16",question=q,
                sources=raw)

    def test_bad_user_input_fails_preflight(self):
        _,raw=report_case()
        questions=[
            "NVDA 2024 매출 성장률",
            "NVDA admin@example.com 매출",
            "NVDA https://bad.example 매출",
            "NVDA\n매출",
            "오늘 날씨",
        ]
        with patch("proofinvest.owner_source_global_agent.run_local_ticker_workflow",
                   side_effect=AssertionError("NOT_AFTER_PREFLIGHT")):
            for q in questions:
                with self.subTest(q=q):
                    self.assertEqual(run(q,sources=raw)["status"],"BLOCKED")
            self.assertEqual(run(sources=raw,as_of="2026-02-30")["status"],
                             "BLOCKED")


if __name__ == "__main__":
    unittest.main()
