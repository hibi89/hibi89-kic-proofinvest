"""One owner-uploaded arbitrary US SEC 4-file question-to-Guard workflow."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.owner_source_global_agent import (
    answer_owner_source_question, verify_owner_source_answer,
)
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
