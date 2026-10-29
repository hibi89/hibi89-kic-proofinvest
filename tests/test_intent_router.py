"""Offline natural-language routing proof: real local tools, no LLM/network."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.intent_router import route_question


class IntentRouterTests(unittest.TestCase):
    def test_conflicting_growth_routes_to_real_decimal_and_guard_reject(self):
        result = route_question("Apple 2025 매출 성장률 20% 검산")
        self.assertEqual(result["selected_intent"], "GROWTH_CHECK")
        self.assertEqual(result["evidence"]["growth_pct"], "6.43")
        self.assertEqual(result["evidence"]["status"], "conflict")
        self.assertEqual(result["guard"]["decision"], "REJECT")
        self.assertEqual(result["reason_code"], "GROWTH_CLAIM_CONFLICT")
        self.assertFalse(result["trade_executed"])

    def test_matching_growth_does_not_upgrade_source_or_risk(self):
        result = route_question("애플 FY2025 매출 성장률 6.43% 확인")
        self.assertEqual(result["evidence"]["status"], "calculated_unverified")
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertEqual(result["status"], "needs_evidence")
        self.assertFalse(result["authenticated_external_source"])

    def test_filing_before_date_fails_closed(self):
        result = route_question("Apple 성장률 6.43% 2025-10-30")
        self.assertEqual(result["selected_intent"], "GROWTH_CHECK")
        self.assertEqual(result["evidence"]["status"], "unavailable")
        self.assertEqual(result["evidence"]["reason_code"], "FILING_AFTER_AS_OF")
        self.assertEqual(result["guard"]["decision"], "HOLD")

    def test_source_is_metadata_not_authenticated_filing(self):
        result = route_question("Apple 2025 공시 원문 근거 알려줘")
        self.assertEqual(result["selected_intent"], "SOURCE_REVIEW")
        self.assertEqual(result["status"], "needs_authentication")
        self.assertIn("MANUAL_EXCERPT", result["reason_code"])
        self.assertIn("0000320193-25-000079", result["evidence"]["accession"])
        self.assertFalse(result["authenticated_external_source"])
        self.assertEqual(result["tool_calls"], ["run_curated_apple_demo"])

    def test_risk_never_invents_ratio(self):
        result = route_question("Apple 2025 부채비율 위험 진단")
        self.assertEqual(result["selected_intent"], "RISK_CHECK")
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertIsNone(result["evidence"]["ratio_pct"])
        self.assertFalse(result["evidence"]["risk_calculated"])
        self.assertEqual(result["tool_calls"], ["evaluate_sec_guard"])

    def test_ambiguous_and_missing_slots_skip_tools(self):
        cases = [
            ("Apple 매출 성장률과 부채 위험", "AMBIGUOUS_OR_MISSING_INTENT"),
            ("Apple 어떻게 투자하지?", "AMBIGUOUS_OR_MISSING_INTENT"),
            ("2025 매출 성장률 20%", "MISSING_ISSUER"),
            ("Apple 매출 성장률 20% 25%", "MULTIPLE_GROWTH_CLAIMS"),
            ("Apple 부채 2025-11-01 2025-10-30", "MULTIPLE_AS_OF_DATES"),
        ]
        for question, code in cases:
            with self.subTest(question=question):
                result = route_question(question)
                self.assertEqual(result["reason_code"], code)
                self.assertEqual(result["tool_calls"], [])
                self.assertIsNotNone(result["question_to_user"])

    def test_invalid_and_unsupported_targets_skip_tools(self):
        for question in (None, "", "x" * 241, "Apple\n매출 성장률",
                         "삼성 매출 성장률 20%", "Apple FY2024 매출 성장률"):
            with self.subTest(question=question):
                result = route_question(question)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["tool_calls"], [])

    def test_strict_tool_budget_and_no_side_effects_or_model(self):
        with tempfile.TemporaryDirectory(prefix="kic-router-test-") as home:
            with patch.dict(os.environ, {"HOME": home}):
                results = [
                    route_question("Apple 2025 매출 20%"),
                    route_question("Apple 공시 출처"),
                    route_question("Apple risk"),
                    route_question("Apple 성장률 20%"),
                ]
                self.assertEqual(list(Path(home).iterdir()), [])
        self.assertEqual(results[0], results[3])
        for result in results:
            self.assertLessEqual(len(result["tool_calls"]), result["tool_budget"])
            self.assertEqual(result["external_tool_calls"], 0)
            self.assertFalse(result["ai_agent_executed"])
            self.assertFalse(result["live_api_called"])
            self.assertFalse(result["trade_executed"])
            self.assertFalse(result["source_rights_verified"])
            self.assertFalse(result["official_contest_submission"])
            self.assertNotEqual(result.get("guard", {}).get("decision") if result["guard"] else None,
                                "APPROVE")

    def test_cli_json_contract(self):
        proc = subprocess.run(
            [sys.executable, "-m", "proofinvest.intent_router",
             "--question", "Apple FY2025 매출 성장률 20%"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["guard"]["decision"], "REJECT")
        self.assertEqual(len(data["tool_calls"]), 2)


if __name__ == "__main__":
    unittest.main()
