"""P122 actual bounded offline pipeline, trace and independent replay."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from proofinvest import ticker_sec_transport as transport
from proofinvest.ticker_local_workflow import run_local_ticker_workflow
from proofinvest.ticker_local_report import verify_local_report
from tests.test_ticker_local_report_replay import report_case
from tests.test_ticker_market_industry_bridge import scenario


class LocalTickerWorkflowTests(unittest.TestCase):
    def test_exact_source_pipeline_trace_and_redacted_report(self):
        _, raws = report_case()
        before = deepcopy(raws)
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("REAL SEC HTTP FORBIDDEN")) as net:
            workflow = run_local_ticker_workflow(
                ticker="NVDA", as_of="2025-10-16", sources=raws)
        net.assert_not_called()
        self.assertEqual(workflow["status"], "READY_FOR_HUMAN_REVIEW_UNVERIFIED")
        self.assertEqual(workflow["tool_calls_executed"], 7)
        self.assertEqual(len(workflow["tool_trace"]), 7)
        self.assertEqual([x["tool"] for x in workflow["tool_trace"]], [
            "prepare_local_ticker_sources", "inspect_collected_annual_revenue",
            "inspect_original_guard_preview", "inspect_ticker_engine_b",
            "evaluate_ticker_a_c",
            "make_local_report", "verify_local_report",
        ])
        self.assertTrue(all(x["accepted"] and x["network_requests"] == 0
                            for x in workflow["tool_trace"]))
        self.assertEqual(workflow["revenue"]["growth_pct"], "100.00")
        self.assertEqual(workflow["original"]["guard_preview"]["decision"], "HOLD")
        self.assertEqual(workflow["report"]["guard_policy_preview"], "HOLD")
        self.assertEqual(verify_local_report(
            workflow["report"], sources=raws)["status"], "PASS")
        self.assertEqual(workflow["report"]["source_rights_ledger"]["status"],
                         "EXTERNAL_USE_BLOCKED_RIGHTS_NOT_VERIFIED")
        self.assertFalse(workflow["source_rights_verified"])
        self.assertFalse(workflow["ai_agent_executed"])
        self.assertFalse(workflow["trade_executed"])
        self.assertFalse(workflow["guard_executed"])
        self.assertFalse(workflow["audit_written"])
        self.assertEqual(raws, before)
        rendered = json.dumps(workflow)
        self.assertNotIn("<html", rendered)
        self.assertNotIn("PRIVATE_BYTES", rendered)

    def test_wrong_issuer_and_fourth_input_stop_before_financial_or_guard(self):
        _, raws = report_case()
        for changes in (
            dict(raws, companyfacts=b"{}"),
            dict(raws, original_10k=b"invalid"),
            {"ticker_map": raws["ticker_map"]},
        ):
            with self.subTest(keys=set(changes)):
                w = run_local_ticker_workflow(
                    ticker="NVDA", as_of="2025-10-16", sources=changes)
                self.assertEqual(w["status"], "BLOCKED")
                self.assertIsNone(w["report"])
                self.assertFalse(w["guard_executed"])
                self.assertFalse(w["official_contest_submission"])
                self.assertLess(w["tool_calls_executed"], 7)
        wrong_ticker = run_local_ticker_workflow(
            ticker="AAPL", as_of="2025-10-16", sources=raws)
        self.assertEqual(wrong_ticker["reason_code"],
                         "SOURCE_IDENTITY_OR_FILING_UNAVAILABLE")
        self.assertEqual(wrong_ticker["tool_calls_executed"], 1)

    def test_bounded_pipeline_optional_market_industry_inputs_and_no_license(self):
        _, raw, m, c = scenario()
        result = run_local_ticker_workflow(
            ticker="NVDA", as_of="2026-02-01", sources=raw,
            market_json=json.dumps(m).encode(),
            industry_json=json.dumps(c).encode())
        self.assertEqual(result["status"], "READY_FOR_HUMAN_REVIEW_UNVERIFIED")
        self.assertEqual(result["supplementary"]["engine_a"]["status"],
                         "REPORTED_UNVERIFIED")
        self.assertEqual(result["supplementary"]["engine_c"]["status"],
                         "OBSERVED_COMPARISON_UNVERIFIED")
        self.assertFalse(result["report"]["source_rights_ledger"]["external_sharing_allowed"])
        self.assertEqual(result["tool_calls_executed"], result["tool_budget"])

    def test_invalid_source_or_preview_blocks_followup_calls(self):
        _, raws = report_case()
        for changed in (
            dict(raws, ticker_map="untrusted string"),
            dict(raws, original_10k=None),
        ):
            out = run_local_ticker_workflow(
                ticker="NVDA", as_of="2025-10-16", sources=changed)
            self.assertEqual(out["tool_calls_executed"], 0)
            self.assertIsNone(out["report"])
        from proofinvest import ticker_local_workflow as workflow
        with patch.object(
            __import__("proofinvest.ticker_sec_original_guard_preview",
                       fromlist=["inspect_original_guard_preview"]),
            "inspect_original_guard_preview",
            return_value={"status": "UNAVAILABLE", "guard_preview": None},
        ):
            out = workflow.run_local_ticker_workflow(
                ticker="NVDA", as_of="2025-10-16", sources=raws)
        self.assertEqual(out["reason_code"], "ORIGINAL_GUARD_REVIEW_UNAVAILABLE")
        self.assertEqual(out["tool_calls_executed"], 3)
        self.assertIsNone(out["report"])

    def test_report_replay_disagreement_does_not_emit_successful_report(self):
        _, raw = report_case()
        from proofinvest import ticker_local_report
        with patch.object(ticker_local_report, "verify_local_report",
                          return_value={"status": "FAIL",
                                        "reason_code": "REPORT_SEMANTIC_REPLAY_MISMATCH"}):
            w = run_local_ticker_workflow(
                ticker="NVDA", as_of="2025-10-16", sources=raw)
        self.assertEqual(w["reason_code"], "INDEPENDENT_REPLAY_FAILED")
        self.assertEqual(w["status"], "BLOCKED")
        self.assertIsNone(w["report"])
        self.assertEqual(w["tool_calls_executed"], 7)


if __name__ == "__main__":
    unittest.main()
