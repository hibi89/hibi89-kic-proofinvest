"""KUODRA P18: strict iXBRL alternative revenue concepts, units, encoding.

Only offline SEC-shaped fixtures. No SEC, LLM, local user files or market data.
"""
from __future__ import annotations

from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.guard_audit import GuardAuditStore
from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
    synthetic_submissions, synthetic_companyfacts,
)
from proofinvest.kic_dl_original_demo import PHRASE
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.ixbrl_revenue_review import review_inline_annual_revenue
from proofinvest.numeric_literal_anchor import find_numeric_literals_in_html_text
from proofinvest.sec_companyfacts import TAG, verify_sec_annual_revenue
from test_ixbrl_revenue_review import xhtml


def alternate(concept: str, *, current_num="2", prior_num="1",
              values=(200, 100)):
    facts = synthetic_companyfacts()
    gaap = facts["facts"]["us-gaap"]
    gaap[concept] = gaap.pop(TAG)
    for row in gaap[concept]["units"]["USD"]:
        if row["end"] == "2025-09-30":
            row["val"] = values[0]
        elif row["end"] == "2024-09-30":
            row["val"] = values[1]
    raw = xhtml(current_num=current_num, prior_num=prior_num)
    raw = raw.replace(TAG.encode(), concept.encode())
    verdict = verify_sec_annual_revenue(
        facts, cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
        current_end="2025-09-30", prior_end="2024-09-30", as_of=AS_OF,
    )
    return raw, facts, verdict


def check(raw, facts, verdict):
    return review_inline_annual_revenue(
        raw, companyfacts=facts, verdict=verdict, cik=SYNTHETIC_CIK,
    )


class StrictInlineMultiConceptTests(unittest.TestCase):
    def test_revenues_selected_from_actual_numeric_verdict(self):
        raw, facts, verdict = alternate("Revenues")
        self.assertEqual(verdict["revenue_concept"], "Revenues")
        value = check(raw, facts, verdict)
        self.assertEqual(value["status"],
                         "local_ixbrl_revenue_context_match_unverified")
        self.assertEqual(value["revenue_concept"], "Revenues")
        self.assertTrue(all(x["amount_matches_companyfacts_input"]
                            for x in value["periods"]))
        self.assertFalse(value["source_authenticated"])
        self.assertFalse(value["financial_facts_authenticated"])

    def test_sales_revenue_net_alternative_supported_without_primary(self):
        raw, facts, verdict = alternate("SalesRevenueNet")
        value = check(raw, facts, verdict)
        self.assertEqual(value["status"],
                         "local_ixbrl_revenue_context_match_unverified")
        self.assertEqual(value["revenue_concept"], "SalesRevenueNet")

    def test_exact_decimal_comma_scale_and_currency(self):
        raw, facts, verdict = alternate(
            "Revenues", current_num="2,000", prior_num="1,000",
            values=(200000, 100000),
        )
        value = check(raw, facts, verdict)
        self.assertEqual(value["status"],
                         "local_ixbrl_revenue_context_match_unverified")
        self.assertEqual([p["scale_exponent"] for p in value["periods"]], [2, 2])
        self.assertTrue(all(p["unit"] == "USD" for p in value["periods"]))
        self.assertFalse(value["precision_independently_verified"])
        # P17 plain numeric scanner deliberately DOES NOT infer hidden
        # iXBRL scale from comma-formatted text.
        number = find_numeric_literals_in_html_text(
            raw, prior_amount="100000", current_amount="200000",
        )
        self.assertEqual(number["status"], "unavailable")

    def test_original_primary_tag_cannot_impersonate_selected_fallback(self):
        raw, facts, verdict = alternate("Revenues")
        wrong_name = raw.replace(b"us-gaap:Revenues",
                                 b"us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax")
        self.assertEqual(check(wrong_name, facts, verdict)["reason_code"],
                         "MISSING_OR_AMBIGUOUS_INLINE_REVENUE_FACTS")

    def test_conflicting_scaled_value_still_rejected(self):
        raw, facts, verdict = alternate(
            "Revenues", current_num="2,001", prior_num="1,000",
            values=(200000, 100000),
        )
        self.assertEqual(check(raw, facts, verdict)["reason_code"],
                         "CONFLICTING_IXBRL_COMPANYFACTS_AMOUNT")

    def test_wrong_unit_and_unsupported_decimals_refused(self):
        raw, facts, verdict = alternate("Revenues")
        wrong_unit = raw.replace(b'contextRef="cur" unitRef="usd"',
                                 b'contextRef="cur" unitRef="shares"')
        self.assertEqual(check(wrong_unit, facts, verdict)["reason_code"],
                         "UNSUPPORTED_IXBRL_CURRENCY_UNIT")
        no_precision = raw.replace(b'decimals="0"', b"", 1)
        self.assertEqual(check(no_precision, facts, verdict)["reason_code"],
                         "UNSUPPORTED_IXBRL_VALUE_SCALE_OR_FORMAT")

    def test_duplicate_same_period_ixbrl_fact_is_ambiguous(self):
        raw, facts, verdict = alternate("Revenues")
        duplicate = (
            b'<ix:nonFraction name="us-gaap:Revenues" contextRef="cur" '
            b'unitRef="usd" scale="2" decimals="0">2</ix:nonFraction>'
        )
        raw = raw.replace(b"</body>", duplicate + b"</body>")
        self.assertEqual(check(raw, facts, verdict)["reason_code"],
                         "MISSING_OR_AMBIGUOUS_INLINE_REVENUE_FACTS")

    def test_wrong_or_missing_selected_concept_fails_closed(self):
        raw, facts, verdict = alternate("Revenues")
        for changed in (
            {**verdict, "revenue_concept": "UnexpectedRevenue"},
            {k: v for k, v in verdict.items() if k != "revenue_concept"},
            {**verdict, "revenue_concept": TAG},
        ):
            with self.subTest(c=changed.get("revenue_concept")):
                self.assertEqual(check(raw, facts, changed)["reason_code"],
                                 "COMPANYFACTS_PERIODS_AMBIGUOUS")

    def test_utf8_bom_and_utf8_xml_declaration_accepted(self):
        raw, facts, verdict = alternate("Revenues")
        encoded = (b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>\n'
                   + raw)
        self.assertEqual(check(encoded, facts, verdict)["status"],
                         "local_ixbrl_revenue_context_match_unverified")

    def test_latin1_xml_declaration_rejected_even_if_ascii_only(self):
        raw, facts, verdict = alternate("Revenues")
        for encoding in (b"ISO-8859-1", b"windows-1252", b"utf-16"):
            with self.subTest(encoding=encoding):
                xml = b'<?xml version="1.0" encoding="' + encoding + b'"?>' + raw
                self.assertEqual(check(xml, facts, verdict)["reason_code"],
                                 "UNSUPPORTED_XML_ENCODING_DECLARATION")

    def test_invalid_utf8_rejected_before_xml_parser(self):
        raw, facts, verdict = alternate("Revenues")
        malformed = raw.replace(b"TEST_LITERAL_SOURCE_SPAN",
                                b"TEST_LITERAL_SOURCE_SPAN\xff")
        self.assertEqual(check(malformed, facts, verdict)["reason_code"],
                         "NOT_STRICT_UTF8_XHTML")

    def test_sec_packet_to_guard_sqlite_with_fallback_revenue(self):
        raw, facts, verdict = alternate("Revenues")
        with tempfile.TemporaryDirectory(prefix="kuodra-p18-") as td:
            db = Path(td) / "audit.sqlite"
            with patch("urllib.request.build_opener",
                       side_effect=AssertionError("UNAPPROVED_HTTP")) as client:
                report = review_local_sec_with_guard(
                    submissions_json=synthetic_submissions(),
                    companyfacts_json=json.dumps(facts).encode(),
                    original_filing=raw, cik=SYNTHETIC_CIK,
                    accession=SYNTHETIC_ACCESSION,
                    as_of=AS_OF, collected_at=COLLECTED_AT,
                    current_end="2025-09-30", prior_end="2024-09-30",
                    needle=PHRASE, audit_db_path=db, run_id="p18-fallback-01",
                    required_review_intent="SOURCE_REVIEW",
                )
            client.assert_not_called()
            self.assertEqual(report["verification"]["revenue_concept"], "Revenues")
            self.assertEqual(report["verification"]["growth_pct"], "100.00")
            self.assertEqual(report["guard"]["decision"], "HOLD")
            self.assertTrue(report["risk"]["corroboration"]["ixbrl_context_match"])
            self.assertFalse(report["risk"]["source_authenticated"])
            self.assertTrue(report["audit_chain_valid"])
            self.assertTrue(GuardAuditStore(db).verify_chain())


if __name__ == "__main__":
    unittest.main()
