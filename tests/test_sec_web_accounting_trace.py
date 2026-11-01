"""P90 deterministic accounting trace, provenance safety and browser UI."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.sec_web_accounting_trace import (
    build_accounting_trace, canonical_json, export_accounting_trace,
)


class AccountingTraceTest(unittest.TestCase):
    def test_full_reproducible_source_math_no_provider_http(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_HTTP_ALLOWED")) as http:
            report = build_accounting_trace()
            exported = export_accounting_trace(report)
        http.assert_not_called()
        self.assertEqual(exported, export_accounting_trace(build_accounting_trace()))
        self.assertLessEqual(len(exported), 16384)
        restored = json.loads(exported)
        self.assertEqual(report, restored)
        self.assertEqual(report["manual_cells_reviewed"], 28)
        self.assertEqual(len(report["trace_cells"]), 7)
        self.assertEqual(report["review_prompt_count"], 3)
        self.assertEqual(
            [(x["code"], x["value"], x["review_prompt"]) for x in report["signals"]],
            [
                ("AR_VS_SALES", "12.63", True),
                ("CFO_TO_INCOME_DROP", "-26.63", True),
                ("FCF_PROXY_VS_SALES", "-15.66", True),
                ("TOTAL_LIABILITIES_TO_EQUITY", "387.22", False),
            ]
        )
        self.assertEqual(report["cash_conversion_intermediates"],
                         {"fy2024_pct": "126.16", "fy2025_pct": "99.53"})
        self.assertEqual(
            report["non_gaap_fcf_intermediates_usd_millions"],
            {"fy2024": "108807", "fy2025": "98767"}
        )
        self.assertTrue(all(row["printed_page_claimed"] in (29, 31, 33)
                            for row in report["trace_cells"]))
        unsigned = {k: v for k, v in report.items() if k != "report_sha256"}
        self.assertEqual(report["report_sha256"],
                         sha256(canonical_json(unsigned)).hexdigest())
        for field in (
            "source_authenticated", "original_sec_bytes_verified",
            "rights_verified", "point_in_time_verified", "misconduct_proven",
            "investment_risk_certified", "real_llm_called",
            "external_http_called", "audit_written", "trade_executed",
            "officially_submitted", "guard_decision_changed",
            "digest_proves_sec_origin",
        ):
            self.assertIs(report[field], False)

    def test_tampering_and_auth_upgrade_refused_before_export(self):
        valid = build_accounting_trace()
        for section, field, value in (
            ("top", "report_sha256", "0" * 64),
            ("top", "source_authenticated", True),
            ("top", "review_prompt_count", 4),
            ("cell", "fy2025_usd_millions", "999999"),
            ("signal", "value", "999.99"),
            ("signal", "review_prompt", False),
        ):
            with self.subTest(field=field):
                bad = deepcopy(valid)
                row = (bad["trace_cells"][0] if section == "cell" else
                       bad["signals"][0] if section == "signal" else bad)
                row[field] = value
                with self.assertRaisesRegex(ValueError, "WEB_B_TRACE_REPORT_TAMPERED"):
                    export_accounting_trace(bad)

    def test_source_mutation_blocks_independent_reconciliation(self):
        from proofinvest.sec_primary_web_brief import build_web_only_brief
        brief = build_web_only_brief()
        with patch("proofinvest.sec_web_accounting_trace.build_web_only_brief",
                   return_value=brief | {"manual_cells_checked": 27}):
            with self.assertRaisesRegex(ValueError, "WEB_B_TRACE_UNTRUSTED_INPUT"):
                build_accounting_trace()
        fake = deepcopy(brief)
        next(x for x in fake["metrics"] if x["key"] == "sales")["fy2025"] = "450000"
        with patch("proofinvest.sec_web_accounting_trace.build_web_only_brief",
                   return_value=fake):
            with self.assertRaisesRegex(
                    ValueError, "WEB_B_TRACE_ARITHMETIC_OR_REVIEW_CONFLICT"):
                build_accounting_trace()

    def test_requires_exact_provenance_and_formula_per_source_key(self):
        report = build_accounting_trace()
        by_key = {c["key"]: c for c in report["trace_cells"]}
        self.assertEqual(by_key["sales"]["fy2025_usd_millions"], "416161")
        self.assertEqual(by_key["sales"]["printed_page_claimed"], 29)
        self.assertEqual(by_key["operating_cashflow"]["fy2024_usd_millions"],
                         "118254")
        self.assertEqual(by_key["operating_cashflow"]["printed_page_claimed"], 33)
        self.assertEqual(by_key["accounts_receivable_net"]["printed_page_claimed"], 31)
        self.assertEqual(report["signals"][2]["input_keys"],
                         ["operating_cashflow", "capex_payments", "sales"])
        self.assertFalse(report["signals"][3]["is_interest_bearing_debt"])


if __name__ == "__main__":
    unittest.main()
