"""P17: SEC iXBRL numeric text boundaries and Guard integration, all offline."""
from __future__ import annotations

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
from proofinvest.local_sec_packet import build_local_sec_review_packet
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.numeric_literal_anchor import find_numeric_literals_in_html_text


def locate(raw: bytes):
    return find_numeric_literals_in_html_text(
        raw, prior_amount="100", current_amount="200",
    )


class NumericIxbrlBoundaryTests(unittest.TestCase):
    def test_hidden_ixbrl_not_numeric_evidence(self):
        raw = (b"<html><body><ix:header><ix:hidden><ix:nonFraction>100"
               b"</ix:nonFraction></ix:hidden></ix:header>"
               b"<p>200</p></body></html>")
        result = locate(raw)
        self.assertEqual(result["reason_code"], "NUMERIC_LITERAL_NOT_IN_HTML_TEXT")
        self.assertFalse(result["financial_facts_authenticated"])

    def test_all_five_ixbrl_suppressed_containers(self):
        for tag in ("ix:hidden", "ix:header", "ix:references",
                    "ix:resources", "ix:exclude"):
            with self.subTest(tag=tag):
                html = ("<html><body><" + tag + ">100</" + tag +
                        "><p>200</p></body></html>").encode()
                self.assertEqual(locate(html)["reason_code"],
                                 "NUMERIC_LITERAL_NOT_IN_HTML_TEXT")

    def test_body_ix_nonfraction_utf8_byte_offsets(self):
        raw = ("<html><body><p>매출</p>"
               "<p><ix:nonFraction>100</ix:nonFraction></p>"
               "<p><ix:nonFraction>200</ix:nonFraction></p></body></html>").encode()
        result = locate(raw)
        self.assertEqual(result["status"], "untrusted_numeric_literals_located")
        for literal, name in (("100", "prior_span"), ("200", "current_span")):
            span = result[name]
            self.assertEqual(span["start_byte"], raw.index(literal.encode()))
            self.assertEqual(raw[span["start_byte"]:span["end_byte_exclusive"]],
                             literal.encode())
        self.assertFalse(result["accounting_units_or_scale_verified"])

    def test_hidden_duplicate_is_not_visible_numeric_ambiguity(self):
        raw = (b"<ix:hidden><ix:nonFraction>100</ix:nonFraction>"
               b"<ix:nonFraction>200</ix:nonFraction></ix:hidden>"
               b"<p>100</p><p>200</p>")
        result = locate(raw)
        self.assertEqual(result["status"], "untrusted_numeric_literals_located")
        self.assertEqual(result["prior_span"]["start_byte"],
                         raw.index(b"<p>100</p>") + len(b"<p>"))
        self.assertFalse(result["financial_facts_authenticated"])

    def test_unclosed_hidden_after_visible_numbers_fails_closed(self):
        result = locate(b"<p>100 200</p><ix:hidden><ix:nonFraction>999")
        self.assertEqual(result["reason_code"],
                         "UNCERTAIN_SUPPRESSED_HTML_REGION")

    def test_unmatched_or_misnested_hidden_closes_fail_closed(self):
        for raw in (
            b"<p>100 200</p></ix:hidden>",
            b"<ix:hidden><ix:header>100</ix:hidden></ix:header><p>200</p>",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(locate(raw)["reason_code"],
                                 "UNCERTAIN_SUPPRESSED_HTML_REGION")

    def test_nested_hidden_script_and_self_closing_metadata(self):
        raw = (b"<ix:header><ix:hidden><script>100</script></ix:hidden>"
               b"</ix:header><ix:hidden/><p>100</p><p>200</p>")
        self.assertEqual(locate(raw)["status"],
                         "untrusted_numeric_literals_located")

    def test_packet_preserves_decimal_but_refuses_hidden_numeric_corrob(self):
        raw = (b"<html><body><p>TEST_LITERAL_SOURCE_SPAN</p>"
               b"<ix:header><ix:hidden>100</ix:hidden></ix:header>"
               b"<p><ix:nonFraction>200</ix:nonFraction></p></body></html>")
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_HTTP")) as network:
            packet = build_local_sec_review_packet(
                submissions_json=synthetic_submissions(),
                companyfacts_json=json.dumps(synthetic_companyfacts()).encode(),
                original_filing=raw, cik=SYNTHETIC_CIK,
                accession=SYNTHETIC_ACCESSION,
                as_of=AS_OF, collected_at=COLLECTED_AT,
                current_end="2025-09-30", prior_end="2024-09-30",
                needle=PHRASE,
            )
        network.assert_not_called()
        self.assertEqual(packet["financial"]["status"], "calculated_unverified")
        self.assertEqual(packet["financial"]["growth_pct"], "100.00")
        self.assertEqual(packet["source"]["numeric_literal_crosscheck"]["status"],
                         "unavailable")
        self.assertFalse(packet["attestations"]["source_authenticated"])

    def test_approved_offline_guard_remains_hold_with_visible_numeric(self):
        raw = (b"<html><body><ix:header><ix:hidden>100</ix:hidden></ix:header>"
               b"<p>TEST_LITERAL_SOURCE_SPAN</p>"
               b"<p><ix:nonFraction>100</ix:nonFraction></p>"
               b"<p><ix:nonFraction>200</ix:nonFraction></p></body></html>")
        with tempfile.TemporaryDirectory(prefix="kuodra-p17-") as root:
            db = Path(root) / "audit.sqlite"
            with patch("urllib.request.build_opener",
                       side_effect=AssertionError("NO_HTTP")) as network:
                result = review_local_sec_with_guard(
                    submissions_json=synthetic_submissions(),
                    companyfacts_json=json.dumps(synthetic_companyfacts()).encode(),
                    original_filing=raw, cik=SYNTHETIC_CIK,
                    accession=SYNTHETIC_ACCESSION,
                    as_of=AS_OF, collected_at=COLLECTED_AT,
                    current_end="2025-09-30", prior_end="2024-09-30",
                    needle=PHRASE, audit_db_path=db, run_id="p17-offline-001",
                    required_review_intent="SOURCE_REVIEW",
                )
            network.assert_not_called()
            self.assertEqual(result["verification"]["growth_pct"], "100.00")
            self.assertEqual(result["guard"]["decision"], "HOLD")
            self.assertTrue(result["risk"]["corroboration"]["numeric_text_match"])
            self.assertFalse(result["risk"]["source_authenticated"])
            self.assertFalse(result["risk"]["trade_authorized"])
            self.assertTrue(GuardAuditStore(db).verify_chain())
            self.assertTrue(result["audit_chain_valid"])


if __name__ == "__main__":
    unittest.main()
