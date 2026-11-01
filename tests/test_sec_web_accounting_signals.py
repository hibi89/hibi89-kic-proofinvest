"""Actual recomputation of manually reviewed Apple FY2025/24 SEC web numbers."""
from __future__ import annotations
from unittest.mock import patch
import json
import unittest

from proofinvest.sec_web_accounting_signals import triage_manual_sec_web


class WebAccountingTriageTest(unittest.TestCase):
    def test_evidence_bound_triage_values_and_no_trust_upgrade(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")) as url:
            result = triage_manual_sec_web()
        url.assert_not_called()
        self.assertEqual(result["schema"], "kuodra.web-manual-accounting-triage.v1")
        self.assertEqual(result["review_prompt_count"], 3)
        p = result["prompts"]
        self.assertEqual(len(p), 4)
        self.assertEqual(p[0]["value_pp"], "12.63")
        self.assertEqual(p[1]["prior_pct"], "126.16")
        self.assertEqual(p[1]["current_pct"], "99.53")
        self.assertEqual(p[1]["change_pp"], "-26.63")
        self.assertEqual(p[2]["current_usd_millions"], "98767")
        self.assertEqual(p[2]["difference_pp"], "-15.66")
        self.assertEqual(p[3]["current_pct"], "387.22")
        self.assertFalse(p[3]["review"])
        self.assertTrue(result["guard_unchanged"])
        self.assertTrue(result["thresholds_heuristic_not_standards"])
        for key in ("misconduct_proven", "source_authenticated",
                    "original_sec_bytes_verified", "rights_verified",
                    "point_in_time_verified", "real_llm_called",
                    "investment_risk_certified", "external_http_called",
                    "audit_written", "trade_executed", "officially_submitted"):
            self.assertIs(result[key], False)
        self.assertEqual(result, json.loads(json.dumps(result, allow_nan=False)))

    def test_untrusted_source_auth_upgrade_is_blocked(self):
        from proofinvest import sec_web_accounting_signals as eng
        from proofinvest.sec_primary_web_brief import build_web_only_brief
        report = build_web_only_brief()
        report["unverified"]["source_authenticated"] = True
        with patch.object(eng, "build_web_only_brief", return_value=report):
            with self.assertRaisesRegex(ValueError, "WEB_B_SOURCE_NOT_TRUSTED"):
                eng.triage_manual_sec_web()

    def test_missing_denominator_is_blocked(self):
        from proofinvest import sec_web_accounting_signals as eng
        from proofinvest.sec_primary_web_brief import build_web_only_brief
        report = build_web_only_brief()
        next(x for x in report["metrics"] if x["key"] == "net_income")["fy2024"] = "0"
        with patch.object(eng, "build_web_only_brief", return_value=report):
            with self.assertRaisesRegex(ValueError, "WEB_B_INVALID_DENOMINATOR"):
                eng.triage_manual_sec_web()


if __name__ == "__main__":
    unittest.main()
