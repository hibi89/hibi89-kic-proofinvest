"""P78 SEC manual-web claim -> actual demo Guard evaluation; no live sources."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from proofinvest.sec_web_claim_guard_demo import review_manual_web_growth_claim
from proofinvest.sec_primary_web_brief import build_web_only_brief


class SecWebClaimGuardDemoTests(unittest.TestCase):
    def test_thirty_percent_claim_rejected_as_demo_only(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NETWORK_FORBIDDEN")) as net:
            result = review_manual_web_growth_claim("30")
        net.assert_not_called()
        self.assertEqual(result["manual_web_growth_pct"], "6.43")
        self.assertEqual(result["claim_minus_manual_web_pp"], "23.57")
        self.assertEqual(result["numeric_verdict"], "CONFLICT")
        self.assertEqual(result["guard"]["decision"], "REJECT")
        self.assertIn("CLAIM_CONFLICT", result["guard"]["reason_codes"])
        self.assertIn("RISK_UNAVAILABLE", result["guard"]["reason_codes"])
        self.assertTrue(result["guard_performed_only_as_demo"])
        self.assertEqual(result["manual_cells_checked"], 28)
        for key in ("source_authenticated", "original_sec_bytes_verified",
                    "real_sec_a_b_c_end_to_end_verified", "rights_verified",
                    "real_llm_called", "external_http_called",
                    "persistent_audit_written", "trade_executed",
                    "contest_submitted", "financial_misconduct_proven"):
            self.assertIs(result[key], False, key)
        self.assertIs(result["guard"]["source_authenticated"], False)
        self.assertIs(result["guard"]["human_approved"], False)

    def test_matching_calculation_is_hold_without_risk_and_real_origin(self):
        x = review_manual_web_growth_claim("6.43")
        self.assertEqual(x["numeric_verdict"], "VERIFIED")
        self.assertTrue(x["numeric_verdict_not_issuer_authentication"])
        self.assertEqual(x["guard"]["decision"], "HOLD")
        self.assertEqual(x["claim_minus_manual_web_pp"], "0.00")
        self.assertIn("RISK_UNAVAILABLE", x["guard"]["reason_codes"])
        self.assertNotIn("CLAIM_CONFLICT", x["guard"]["reason_codes"])
        self.assertFalse(x["source_authenticated"])

    def test_missing_claim_is_hold_and_unavailable(self):
        x = review_manual_web_growth_claim()
        self.assertIsNone(x["claim_growth_pct"])
        self.assertIsNone(x["claim_minus_manual_web_pp"])
        self.assertEqual(x["numeric_verdict"], "UNAVAILABLE")
        self.assertEqual(x["guard"]["decision"], "HOLD")
        self.assertIn("CLAIM_UNAVAILABLE", x["guard"]["reason_codes"])
        self.assertIn("RISK_UNAVAILABLE", x["guard"]["reason_codes"])

    def test_reject_malformed_and_oversized_claim_without_running_source(self):
        invalid = ("NaN", "Infinity", "1e5", "6.430", "+30", "030",
                   "1000", "-101", "", " 30", "30;rm", "3" * 1000,
                   "30<script>", 30, {}, True)
        with patch("proofinvest.sec_web_claim_guard_demo.build_web_only_brief",
                   side_effect=AssertionError("SOURCE_MUST_NOT_BE_READ")) as source:
            for case in invalid:
                with self.subTest(claim=repr(case)), self.assertRaises(ValueError):
                    review_manual_web_growth_claim(case)
            source.assert_not_called()

    def test_forged_web_provenance_and_financial_data_blocked(self):
        clean = build_web_only_brief()
        for mutate in (
            lambda x: x["unverified"].__setitem__("source_authenticated", True),
            lambda x: x["unverified"].pop("trade_executed"),
            lambda x: x["analysis"].__setitem__("revenue_growth_pct", "30.00"),
            lambda x: x["metrics"][0].__setitem__("fy2025", "1"),
            lambda x: x.__setitem__("manual_cells_checked", 0),
        ):
            forged = copy.deepcopy(clean)
            mutate(forged)
            with self.subTest(forged=forged.get("analysis", {})), patch(
                "proofinvest.sec_web_claim_guard_demo.build_web_only_brief",
                return_value=forged
            ):
                with self.assertRaises(ValueError):
                    review_manual_web_growth_claim("30")

    def test_cli_three_outcomes_and_sanitized_rejection(self):
        base = [sys.executable, "-B", "-m",
                "proofinvest.sec_web_claim_guard_demo"]
        for args, decision in (
            (["--claimed-growth-pct", "30"], "REJECT"),
            (["--claimed-growth-pct", "6.43"], "HOLD"),
            ([], "HOLD"),
        ):
            with self.subTest(args=args):
                run = subprocess.run(base + args, capture_output=True,
                                     text=True, timeout=30)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                data = json.loads(run.stdout)
                self.assertEqual(data["guard"]["decision"], decision)
                self.assertFalse(data["source_authenticated"])
                self.assertFalse(data["external_http_called"])
        bad = subprocess.run(base + ["--claimed-growth-pct", "NaN"],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(json.loads(bad.stdout)["status"], "BLOCKED")
        self.assertNotIn("Traceback", bad.stderr)


if __name__ == "__main__":
    unittest.main()
