"""Strict iXBRL XHTML local structural revenue context tests."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from proofinvest.ixbrl_revenue_review import review_inline_annual_revenue
from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE
from proofinvest.local_sec_packet import build_local_sec_review_packet
from proofinvest.sec_companyfacts import verify_sec_annual_revenue


def xhtml(
    *, current_num="2", prior_num="1",
    current_unit="usd", current_context="cur",
    current_scale="2", prior_scale="2",
    duplicate="", extra="", current_tag="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
):
    return (f"""<html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
        xmlns:xbrli="http://www.xbrl.org/2003/instance"
        xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
        xmlns:us-gaap="http://fasb.org/us-gaap/2025">
        <body>TEST_LITERAL_SOURCE_SPAN
         <xbrli:context id="cur"><xbrli:entity>
          <xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier>
          </xbrli:entity><xbrli:period><xbrli:startDate>2024-10-01</xbrli:startDate>
          <xbrli:endDate>2025-09-30</xbrli:endDate></xbrli:period></xbrli:context>
         <xbrli:context id="prev"><xbrli:entity>
          <xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier>
          </xbrli:entity><xbrli:period><xbrli:startDate>2023-10-01</xbrli:startDate>
          <xbrli:endDate>2024-09-30</xbrli:endDate></xbrli:period></xbrli:context>
         <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
         <xbrli:unit id="shares"><xbrli:measure>shares</xbrli:measure></xbrli:unit>
         <p><ix:nonFraction name="{current_tag}"
              contextRef="{current_context}" unitRef="{current_unit}" scale="{current_scale}"
              decimals="0">{current_num}</ix:nonFraction></p>
         <p><ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
              contextRef="prev" unitRef="usd" scale="{prior_scale}"
              decimals="0">{prior_num}</ix:nonFraction></p>
          {duplicate}{extra}
         </body></html>""").encode("utf-8")


def review(raw: bytes, facts=None, verdict=None):
    if facts is None:
        facts = synthetic_companyfacts()
    if verdict is None:
        verdict = verify_sec_annual_revenue(
            facts, cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
            current_end="2025-09-30", prior_end="2024-09-30", as_of=AS_OF,
        )
    return review_inline_annual_revenue(
        raw, companyfacts=facts, verdict=verdict, cik=SYNTHETIC_CIK,
    )


class InlineXbrlRevenueTests(unittest.TestCase):
    def test_valid_two_year_context_unit_and_scale(self):
        value = review(xhtml())
        self.assertEqual(value["status"], "local_ixbrl_revenue_context_match_unverified")
        self.assertEqual([p["scale_exponent"] for p in value["periods"]], [2, 2])
        self.assertEqual([p["period_end"] for p in value["periods"]],
                         ["2024-09-30", "2025-09-30"])
        self.assertTrue(all(p["amount_matches_companyfacts_input"] for p in value["periods"]))
        for flag in ("source_authenticated", "financial_facts_authenticated",
                     "xbrl_taxonomy_validated", "context_origin_authenticated",
                     "precision_independently_verified", "sec_network_called"):
            self.assertIs(value[flag], False, flag)

    def test_end_to_end_archive_packet_includes_review_status_without_auth(self):
        raw = xhtml()
        packet = build_local_sec_review_packet(
            submissions_json=synthetic_submissions(),
            companyfacts_json=json.dumps(synthetic_companyfacts()).encode(),
            original_filing=raw, cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
            as_of=AS_OF, collected_at=COLLECTED_AT,
            current_end="2025-09-30", prior_end="2024-09-30", needle=PHRASE,
        )
        self.assertEqual(packet["source"]["ixbrl_revenue_context_review"]["status"],
                         "local_ixbrl_revenue_context_match_unverified")
        self.assertEqual(packet["financial"]["growth_pct"], "100.00")
        self.assertFalse(packet["source"]["span_proves_financial_claim"])
        self.assertTrue(all(x is False for x in packet["attestations"].values()))
        self.assertNotIn("<ix:", json.dumps(packet))

    def test_original_plain_html_is_not_accepted_as_ixbrl(self):
        from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML
        self.assertEqual(review(SYNTHETIC_HTML)["status"], "unavailable")

    def test_wrong_current_amount_rejects_claimed_match(self):
        self.assertEqual(review(xhtml(current_num="3"))["reason_code"],
                         "CONFLICTING_IXBRL_COMPANYFACTS_AMOUNT")

    def test_wrong_unit_rejected(self):
        self.assertEqual(review(xhtml(current_unit="shares"))["reason_code"],
                         "UNSUPPORTED_IXBRL_CURRENCY_UNIT")

    def test_wrong_context_is_not_silently_selected(self):
        self.assertEqual(review(xhtml(current_context="prev"))["reason_code"],
                         "CONFLICTING_IXBRL_COMPANYFACTS_AMOUNT")

    def test_duplicate_current_inline_fact_ambiguous(self):
        dup = ('<ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"'
               ' contextRef="cur" unitRef="usd" scale="2" decimals="0">2</ix:nonFraction>')
        self.assertEqual(review(xhtml(duplicate=dup))["reason_code"],
                         "MISSING_OR_AMBIGUOUS_INLINE_REVENUE_FACTS")

    def test_context_entity_cik_mismatch(self):
        source = xhtml().replace(b"0000000001</xbrli:identifier>",
                                 b"0000000002</xbrli:identifier>")
        self.assertEqual(review(source)["reason_code"], "MALFORMED_CONTEXT_OR_CURRENCY_UNIT")

    def test_wrong_period_start_is_not_accepted(self):
        source = xhtml().replace(b"2024-10-01", b"2024-09-01")
        self.assertEqual(review(source)["reason_code"], "MISSING_OR_AMBIGUOUS_INLINE_REVENUE_FACTS")

    def test_unsupported_negative_scale_and_missing_precision(self):
        self.assertEqual(review(xhtml(current_scale="-6"))["reason_code"],
                         "UNSUPPORTED_IXBRL_VALUE_SCALE_OR_FORMAT")
        self.assertEqual(review(xhtml().replace(b'decimals="0"', b"", 1))["reason_code"],
                         "UNSUPPORTED_IXBRL_VALUE_SCALE_OR_FORMAT")

    def test_ambiguous_or_malformed_companyfacts_source_period(self):
        facts = synthetic_companyfacts()
        rows = facts["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
        rows.append(deepcopy(rows[0]))
        self.assertEqual(review(xhtml(), facts=facts)["reason_code"],
                         "COMPANYFACTS_PERIODS_AMBIGUOUS")

    def test_external_doctype_and_unbounded_xml_forbidden(self):
        self.assertEqual(review(b'<!DOCTYPE foo [<!ENTITY x "1">]>'+xhtml())["reason_code"],
                         "FORBIDDEN_XML_DECLARATION")
        self.assertEqual(review(b"x"*8_000_001)["status"], "unavailable")

    def test_script_text_not_used_in_place_of_ix_nonfraction(self):
        raw = xhtml(current_num="2").replace(b">2</ix:nonFraction>", b">3</ix:nonFraction>")
        raw = raw.replace(b"</body>", b"<script>2</script></body>")
        self.assertEqual(review(raw)["reason_code"], "CONFLICTING_IXBRL_COMPANYFACTS_AMOUNT")

    def test_inline_unit_scale_wins_over_incidental_numeric_literals(self):
        raw = xhtml(current_num="2", prior_num="1")
        res = review(raw)
        self.assertEqual(res["periods"][1]["amount_matches_companyfacts_input"], True)
        self.assertFalse(res["financial_facts_authenticated"])


if __name__ == "__main__":
    unittest.main()
