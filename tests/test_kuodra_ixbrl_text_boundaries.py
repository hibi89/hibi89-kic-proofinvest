"""P16 SEC-shaped Inline XBRL text boundaries: offline proof and anti-leak."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.guard_audit import GuardAuditStore
from proofinvest.kuodra_offline_preflight import inspect_saved_capture_periods
from proofinvest.kuodra_operator_request_draft import build_operator_request_draft
from proofinvest.kuodra_operator_replay import run_offline_proposal_replay
from proofinvest.visible_text_evidence import confirm_html_text_node_literal
from test_kuodra_operator_replay import capture_fixture

TOKEN = "TEST_LITERAL_SOURCE_SPAN"
HIDDEN = "HIDDEN_REVENUE_METADATA_ONLY"
VISIBLE = b'<p><ix:nonFraction name="us-gaap:Revenues">' + TOKEN.encode() + b'</ix:nonFraction></p>'


def _literal(raw: bytes, literal: str = TOKEN):
    offset = raw.find(literal.encode("ascii"))
    return confirm_html_text_node_literal(
        raw, needle=literal,
        expected_start=offset, expected_end=offset + len(literal),
    )


class InlineXbrlBoundaryTests(unittest.TestCase):
    def test_ix_hidden_not_eligible_as_visible_original_text(self):
        raw = (b'<html><body><ix:hidden><ix:nonFraction>' +
               TOKEN.encode() + b'</ix:nonFraction></ix:hidden></body></html>')
        result = _literal(raw)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason_code"],
                         "LITERAL_NOT_IN_ELIGIBLE_HTML_TEXT_NODE")
        self.assertFalse(result["exact_raw_byte_span_verified"])

    def test_ix_header_and_resources_not_eligible(self):
        for tag in ("ix:header", "ix:resources", "ix:references"):
            with self.subTest(tag=tag):
                raw = ("<html><body><" + tag + "><span>" + TOKEN +
                       "</span></" + tag + "></body></html>").encode()
                self.assertEqual(_literal(raw)["status"], "unavailable")

    def test_ix_exclude_not_eligible(self):
        raw = ("<p><ix:exclude>" + TOKEN + "</ix:exclude></p>").encode()
        self.assertEqual(_literal(raw)["status"], "unavailable")

    def test_body_ix_nonfraction_exact_utf8_byte_offsets(self):
        raw = "<html><body><p>한글</p>".encode() + VISIBLE + b"</body></html>"
        out = _literal(raw)
        self.assertEqual(out["status"], "untrusted_html_text_node_literal_located")
        self.assertEqual(raw[out["start_byte"]:out["end_byte_exclusive"]],
                         TOKEN.encode())
        self.assertFalse(out["rendered_visibility_verified"])
        self.assertFalse(out["source_authenticated"])

    def test_unclosed_ix_hidden_fails_closed_even_after_normal_body(self):
        raw = b"<p>" + TOKEN.encode() + b"</p><ix:hidden><ix:nonFraction>OTHER"
        result = _literal(raw)
        self.assertEqual(result["reason_code"], "HTML_TEXT_NODE_PARSE_UNCERTAIN")

    def setUp(self):
        holder = tempfile.TemporaryDirectory(prefix="kuodra-ixbrl-")
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name)
        self.zip = self.root / "source.zip"
        self.db = self.root / "audit.sqlite"

    def _save(self, raw: bytes):
        capture_fixture(self.zip, original=raw)

    def _draft(self, needle=TOKEN, requested_intent="SOURCE_REVIEW"):
        return build_operator_request_draft(
            self.zip, requested_intent=requested_intent,
            current_end="2025-09-30", prior_end="2024-09-30",
            needle=needle, audit_db=self.db, run_id="p16-ix-src",
        )

    def test_preflight_explicit_candidates_do_not_disclose_ix_hidden(self):
        self._save(b"<html><body><ix:header><ix:hidden><ix:nonFraction>" +
                   HIDDEN.encode() +
                   b"</ix:nonFraction></ix:hidden></ix:header>" +
                   VISIBLE + b"</body></html>")
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_HTTP")) as client:
            report = inspect_saved_capture_periods(
                self.zip, show_local_needle_candidates=True)
        client.assert_not_called()
        self.assertEqual(report["status"], "review_candidates_available")
        literals = [x["needle"] for x in report["local_needle_candidates"]]
        self.assertNotIn(HIDDEN, literals)
        self.assertIn(TOKEN, literals)
        self.assertFalse(self.db.exists())

    def test_p15_cannot_draft_from_hidden_ixbrl_only(self):
        self._save(b"<html><body><ix:header><ix:hidden><ix:nonFraction>" +
                   TOKEN.encode() +
                   b"</ix:nonFraction></ix:hidden></ix:header></body></html>")
        result = self._draft()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason_code"],
                         "OPERATOR_NEEDLE_NOT_UNIQUE_TEXT_NODE")
        self.assertFalse(self.db.exists())

    def test_p15_visible_ixbrl_to_guard_sqlite_with_explicit_approval(self):
        self._save(b"<html><body><ix:header><ix:hidden>OTHER_METADATA</ix:hidden>"
                   b"</ix:header>" + VISIBLE + b"</body></html>")
        initial = self.zip.read_bytes()
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_HTTP")) as network:
            draft = self._draft()
            self.assertEqual(draft["status"], "ready_for_operator_review")
            req = draft["operator_request"]
            denied = run_offline_proposal_replay(
                req, {"action": "RUN", "intent": "SOURCE_REVIEW"},
                acknowledge_local_audit_persistence=False)
            self.assertEqual(denied["reason_code"],
                             "EXPLICIT_LOCAL_AUDIT_CONSENT_REQUIRED")
            self.assertFalse(self.db.exists())
            report = run_offline_proposal_replay(
                req, {"action": "RUN", "intent": "SOURCE_REVIEW"},
                acknowledge_local_audit_persistence=True)
        network.assert_not_called()
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["selected_intent"], "SOURCE_REVIEW")
        self.assertTrue(report["operator_source_digests_verified"])
        self.assertTrue(report["source_review"]["exact_raw_byte_span_verified"])
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertEqual(self.zip.read_bytes(), initial)
        self.assertFalse(report["source_authenticated"])

    def test_repeated_hidden_and_body_literal_remains_raw_ambiguous(self):
        self._save(b"<html><body><ix:hidden>" + TOKEN.encode() +
                   b"</ix:hidden>" + VISIBLE + b"</body></html>")
        # Old raw byte-span locator deliberately requires global uniqueness.
        # This P16 change does NOT claim to solve repeated SEC fact strings.
        result = self._draft()
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(self.db.exists())


if __name__ == "__main__":
    unittest.main()
