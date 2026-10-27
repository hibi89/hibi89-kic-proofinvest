"""Tests for conservatively locating two numeric literals in local HTML."""
from __future__ import annotations
import json
import unittest

from proofinvest.numeric_literal_anchor import find_numeric_literals_in_html_text
from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
    synthetic_submissions, synthetic_companyfacts,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.local_sec_packet import build_local_sec_review_packet


def _locate(raw: bytes, prior: str = "100", current: str = "200"):
    return find_numeric_literals_in_html_text(
        raw, prior_amount=prior, current_amount=current,
    )


class NumericLiteralAnchorTests(unittest.TestCase):
    def test_unique_two_numbers_located_at_exact_byte_offsets(self):
        raw = b"<html><body><p>Revenue 100</p><p>Revenue 200</p></body></html>"
        ans = _locate(raw)
        self.assertEqual(ans["status"], "untrusted_numeric_literals_located")
        for number, name in (("100", "prior_span"), ("200", "current_span")):
            p = ans[name]
            self.assertEqual(raw[p["start_byte"]:p["end_byte_exclusive"]], number.encode())
        self.assertTrue(all(v is False for k, v in ans.items() if k.endswith("_verified") or k.endswith("_authenticated")))

    def test_script_style_comment_attributes_not_counted(self):
        raw = (b'<html><head>100</head><script>200</script>'
               b'<style>x{width:100px}</style><body data-x="200">'
               b'<!-- 100 -->No numbers here</body></html>')
        ans = _locate(raw)
        self.assertEqual(ans["status"], "unavailable")
        self.assertEqual(ans["reason_code"], "NUMERIC_LITERAL_NOT_IN_HTML_TEXT")

    def test_reject_number_substrings_decimal_and_thousands(self):
        raw = b"<p>1100 2000 100.2 1,200 plus-100 and 200.5</p>"
        ans = _locate(raw)
        self.assertEqual(ans["status"], "unavailable")

    def test_duplicate_token_fails_closed_instead_of_guess(self):
        raw = b"<p>100 100 200</p>"
        ans = _locate(raw)
        self.assertEqual(ans["reason_code"], "AMBIGUOUS_NUMERIC_LITERAL_OCCURRENCES")

    def test_equal_prior_and_current_cannot_distinguish_period(self):
        ans = _locate(b"<p>100 100</p>", prior="100", current="100")
        self.assertEqual(ans["reason_code"], "IDENTICAL_NUMERIC_LITERALS_AMBIGUOUS")

    def test_invalid_utf8_and_noninteger_amount_unavailable(self):
        self.assertEqual(_locate(b"\xff<p>100 200</p>")["status"], "unavailable")
        self.assertEqual(_locate(b"<p>100 200</p>", prior="100.0")["status"], "unavailable")

    def test_utf8_prefix_preserves_byte_offset_not_character_index(self):
        raw = "<div>매출 100</div><p>비교 200</p>".encode("utf-8")
        ans = _locate(raw)
        self.assertEqual(ans["status"], "untrusted_numeric_literals_located")
        self.assertEqual(ans["current_span"]["start_byte"], raw.index(b"200"))
        self.assertEqual(ans["prior_span"]["start_byte"], raw.index(b"100"))

    def test_local_packet_reports_unavailable_for_old_arbitrary_marker(self):
        receipt = build_local_sec_review_packet(
            submissions_json=synthetic_submissions(),
            companyfacts_json=json.dumps(synthetic_companyfacts()).encode(),
            original_filing=SYNTHETIC_HTML,
            cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
            as_of=AS_OF, collected_at=COLLECTED_AT,
            current_end="2025-09-30", prior_end="2024-09-30", needle=PHRASE,
        )
        self.assertEqual(
            receipt["source"]["numeric_literal_crosscheck"]["status"], "unavailable"
        )
        self.assertFalse(receipt["source"]["span_proves_financial_claim"])

    def test_local_packet_locates_numeric_literals_after_real_archive_roundtrip(self):
        raw = (b"<html><body><p>TEST_LITERAL_SOURCE_SPAN</p>"
               b"<p>Prior 100</p><p>Current 200</p>"
               b"<script>malicious();</script></body></html>")
        packet = build_local_sec_review_packet(
            submissions_json=synthetic_submissions(),
            companyfacts_json=json.dumps(synthetic_companyfacts()).encode(),
            original_filing=raw,
            cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
            as_of=AS_OF, collected_at=COLLECTED_AT,
            current_end="2025-09-30", prior_end="2024-09-30", needle=PHRASE,
        )
        match = packet["source"]["numeric_literal_crosscheck"]
        self.assertEqual(match["status"], "untrusted_numeric_literals_located")
        self.assertEqual(raw[match["prior_span"]["start_byte"]:match["prior_span"]["end_byte_exclusive"]], b"100")
        self.assertEqual(raw[match["current_span"]["start_byte"]:match["current_span"]["end_byte_exclusive"]], b"200")
        self.assertFalse(match["financial_facts_authenticated"])
        self.assertFalse(packet["attestations"]["source_authenticated"])
        self.assertNotIn("malicious();", json.dumps(packet))

    def test_nested_script_head_and_template_do_not_supply_numbers(self):
        raw = b"<head><title>100</title></head><body><template><p>200</p></template></body>"
        self.assertEqual(_locate(raw)["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
