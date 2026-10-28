"""Regression tests for DL extracted text with true raw-content SHA checks.

Never calls real SEC; all source-like bytes below are synthetic.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from disclosure_lightning import core, extract, originals


CIK = "0000320193"
ACC = "0000320193-25-000079"
META = Path(__file__).resolve().parents[1] / "disclosure_lightning/fixtures/kic_apple_handoff_synthetic.json"


@contextlib.contextmanager
def _sqlite_connection(path):
    connection = sqlite3.connect(path)
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
RAW = b"""<!doctype html>
<html>
<head><title>Hidden title</title><style>.hidden { display:none; }</style></head>
<body>
<h1>Visible filing section</h1>
<script>alert('UNTRUSTED SCRIPT');</script>
<p>2025 Revenue &amp; Expenses</p>
<p>Another paragraph</p>
</body></html>"""


class ExtractedFilingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="dl-extract-")
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "dl.sqlite3"
        self.metadata_raw = META.read_bytes()
        indexed = core.index_submissions(
            self.metadata_raw, cik=CIK, as_of="2025-11-01",
            forms=core.parse_forms("10-K"),
            provenance="SEC_HTTPS_RESPONSE",  # mocked transport-shaped provenance
            collected_at="2025-11-01T10:30:00Z",
        )
        core.save_index(self.db, self.metadata_raw, indexed)
        self.receipt = originals.locate_original(self.db, cik=CIK, accession=ACC)
        self.saved = originals.persist_original(
            db_path=self.db, receipt=self.receipt, raw=RAW,
            kind="text/html", origin="SEC_HTTPS_RESPONSE_UNVERIFIED"
        )

    def run_from_saved(self):
        return extract.from_saved_original(
            db_path=self.db, cik=CIK, accession=ACC,
            sha256=self.saved["filing_sha256"]
        )

    def test_html_visible_fragments_and_provenance(self):
        r = self.run_from_saved()
        self.assertEqual(r["schema"], "disclosure-lightning.extracted-text.v1")
        self.assertEqual(r["block_count"], 3)
        self.assertEqual(
            [block["text"] for block in r["blocks"]],
            ["Visible filing section", "2025 Revenue & Expenses", "Another paragraph"]
        )
        self.assertTrue(r["complete_text_extracted"])
        self.assertEqual(r["filing_sha256"], hashlib.sha256(RAW).hexdigest())
        self.assertFalse(r["source_authenticity_verified"])
        self.assertFalse(r["suitable_for_automatic_financial_facts"])
        self.assertEqual(r["source_locator_accuracy"],
                         "HTML_UTF8_LITERAL_BYTE_SPANS_WITH_LINE_HINT_FALLBACK")
        self.assertEqual([b["exact_raw_byte_range_verified"] for b in r["blocks"]],
                         [True, False, True])
        for block in r["blocks"]:
            self.assertGreater(block["source_locator"]["line"], 0)
            self.assertEqual(block["text_sha256"], hashlib.sha256(
                block["text"].encode()).hexdigest())
        self.assertFalse(any("SCRIPT" in b["text"] or "Hidden" in b["text"] for b in r["blocks"]))
        for block in (r["blocks"][0], r["blocks"][2]):
            locator = block["source_locator"]
            span = RAW[locator["start_byte"]:locator["end_byte_exclusive"]]
            self.assertEqual(span.decode("utf-8"), block["text"])
            self.assertEqual(block["raw_span_sha256"], hashlib.sha256(span).hexdigest())

    def test_utf8_html_byte_spans_count_multibyte_and_bom_offsets(self):
        raw = (b"\xef\xbb\xbf<html>\n<p>" + "  매출  2025 ".encode("utf-8")
               + b"</p>\n<p>A &amp; B</p></html>")
        result = extract.extract_bytes(
            raw, content_type="text/html",
            filing_sha256=hashlib.sha256(raw).hexdigest(),
            issuer_cik=CIK, accession=ACC,
            source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED",
        )
        self.assertEqual([b["text"] for b in result["blocks"]], ["매출 2025", "A & B"])
        first, entity_text = result["blocks"]
        locator = first["source_locator"]
        self.assertEqual(locator["type"], "UTF8_HTML_TEXT_NODE_BYTE_SPAN")
        self.assertEqual(locator["start_byte"], raw.index("  매출".encode("utf-8")))
        self.assertEqual(raw[locator["start_byte"]:locator["end_byte_exclusive"]],
                         "  매출  2025 ".encode("utf-8"))
        self.assertFalse(entity_text["exact_raw_byte_range_verified"])

    def test_plain_text_line_numbers_and_no_evidence_upgrade(self):
        raw = b"HEADER\n\nFinancial item 100\nAnother line\n"
        result = extract.extract_bytes(
            raw, content_type="text/plain", filing_sha256=hashlib.sha256(raw).hexdigest(),
            issuer_cik=CIK, accession=ACC, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED"
        )
        self.assertEqual([b["source_locator"]["line"] for b in result["blocks"]], [1, 3, 4])
        self.assertEqual(result["block_count"], 3)
        self.assertEqual(result["extraction_method"], "utf8-lines")
        self.assertFalse(result["source_authenticity_verified"])

    def test_utf8_plain_text_has_exact_raw_line_byte_spans(self):
        # UTF-8 BOM, CRLF, multi-byte Hangul, blank lines and clean-text
        # whitespace normalization must not change the recorded RAW offset.
        raw = b"\xef\xbb\xbf" + "  매출  2025 \r\n\r\nRevenue & Expenses\n".encode("utf-8")
        receipt = extract.extract_bytes(
            raw, content_type="text/plain",
            filing_sha256=hashlib.sha256(raw).hexdigest(),
            issuer_cik=CIK, accession=ACC, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED",
        )
        self.assertEqual(receipt["source_locator_accuracy"],
                         "EXACT_RAW_LINE_BYTE_SPANS_UNVERIFIED_SOURCE")
        self.assertEqual([b["text"] for b in receipt["blocks"]],
                         ["매출 2025", "Revenue & Expenses"])
        self.assertEqual([b["source_locator"]["line"] for b in receipt["blocks"]], [1, 3])
        first, second = receipt["blocks"]
        self.assertEqual(first["source_locator"]["start_byte"], 3)
        self.assertEqual(second["source_locator"]["start_byte"],
                         raw.index(b"Revenue"))
        for block in receipt["blocks"]:
            self.assertTrue(block["exact_raw_byte_range_verified"])
            locator = block["source_locator"]
            span = raw[locator["start_byte"]:locator["end_byte_exclusive"]]
            self.assertEqual(block["raw_span_sha256"], hashlib.sha256(span).hexdigest())
        self.assertTrue(raw[first["source_locator"]["start_byte"]:
                            first["source_locator"]["end_byte_exclusive"]].endswith(b"\r\n"))
        self.assertFalse(receipt["source_authenticity_verified"])
        self.assertFalse(receipt["suitable_for_automatic_financial_facts"])

    def test_byte_spans_survive_candidate_search_without_certifying_claims(self):
        raw = "Revenue 100\n".encode("utf-8")
        receipt = extract.extract_bytes(
            raw, content_type="text/plain",
            filing_sha256=hashlib.sha256(raw).hexdigest(), issuer_cik=CIK,
            accession=ACC, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED",
        )
        found = extract.find_evidence_candidates(receipt, term="Revenue")
        self.assertEqual(found["returned"], 1)
        candidate = found["candidates"][0]
        self.assertTrue(candidate["exact_raw_byte_range_verified"])
        self.assertEqual(candidate["source_locator"]["start_byte"], 0)
        self.assertEqual(candidate["source_locator"]["end_byte_exclusive"], len(raw))
        self.assertFalse(candidate["financial_claim_verified"])
        self.assertFalse(found["source_authenticity_verified"])

    def test_skipped_long_raw_line_keeps_next_line_correct_offset(self):
        raw = b"X" * 1800 + b"\nRevenue 200\n"
        receipt = extract.extract_bytes(
            raw, content_type="text/plain",
            filing_sha256=hashlib.sha256(raw).hexdigest(),
            issuer_cik=CIK, accession=ACC, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED",
        )
        self.assertTrue(receipt["truncated"])
        self.assertEqual(receipt["block_count"], 1)
        block = receipt["blocks"][0]
        self.assertEqual(block["source_locator"]["line"], 2)
        self.assertEqual(block["source_locator"]["start_byte"], 1801)
        self.assertEqual(block["source_locator"]["end_byte_exclusive"], len(raw))

    def test_declared_windows_1252_html_is_decoded_without_issuer_attestation(self):
        for label in ("windows-1252", "ISO-8859-1"):
            with self.subTest(label=label):
                raw = (
                    '<html><head><meta charset="' + label +
                    '"></head><body><p>Revenue '
                ).encode("ascii") + b"\x93increase\x94</p></body></html>"
                r = extract.extract_bytes(
                    raw, content_type="text/html",
                    filing_sha256=hashlib.sha256(raw).hexdigest(),
                    issuer_cik=CIK, accession=ACC,
                    source_uri=self.receipt["source_uri"],
                    input_origin="OFFLINE_FILE_UNVERIFIED",
                )
                self.assertEqual(r["decoded_encoding"], "windows-1252")
                self.assertEqual(r["html_meta_declared_charset"], label.lower())
                self.assertFalse(r["charset_claim_verified"])
                self.assertEqual(r["blocks"][0]["text"], "Revenue “increase”")
                self.assertFalse(r["blocks"][0]["exact_raw_byte_range_verified"])
                self.assertFalse(r["source_authenticity_verified"])
                self.assertFalse(r["suitable_for_automatic_financial_facts"])

    def test_legacy_html_http_equiv_charset_supported_but_not_guessed(self):
        raw = (
            b'<html><head><meta http-equiv="Content-Type" '
            b'content="text/html; charset=windows-1252"></head><body>'
            b'<p>Revenue \x93change\x94</p></body></html>'
        )
        r = extract.extract_bytes(
            raw, content_type="text/html", filing_sha256=hashlib.sha256(raw).hexdigest(),
            issuer_cik=CIK, accession=ACC, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED",
        )
        self.assertEqual(r["blocks"][0]["text"], "Revenue “change”")
        self.assertEqual(r["decoded_encoding"], "windows-1252")
        raw_no_declaration = b"<p>Revenue \x93change\x94</p>"
        with self.assertRaisesRegex(ValueError, "ENCODING"):
            extract.extract_bytes(
                raw_no_declaration, content_type="text/html",
                filing_sha256=hashlib.sha256(raw_no_declaration).hexdigest(),
                issuer_cik=CIK, accession=ACC,
                source_uri=self.receipt["source_uri"],
                input_origin="OFFLINE_FILE_UNVERIFIED",
            )

    def test_conflicting_bom_and_unknown_html_charset_rejected(self):
        for raw, reason in (
            (b'\xef\xbb\xbf<meta charset="windows-1252"><p>Revenue</p>',
             "CONFLICTING"),
            (b'<meta charset="shift_jis"><p>Revenue</p>',
             "UNSUPPORTED_DECLARED"),
            (b'<meta charset="windows-1252"><p>\x81</p>',
             "ENCODING"),
        ):
            with self.subTest(raw=raw[:30]), self.assertRaisesRegex(ValueError, reason):
                extract.extract_bytes(
                    raw, content_type="text/html",
                    filing_sha256=hashlib.sha256(raw).hexdigest(),
                    issuer_cik=CIK, accession=ACC,
                    source_uri=self.receipt["source_uri"],
                    input_origin="OFFLINE_FILE_UNVERIFIED",
                )

    def test_data_charset_attribute_is_not_an_encoding_declaration(self):
        raw = b'<meta data-charset="windows-1252"><p>Revenue \x93growth\x94</p>'
        with self.assertRaisesRegex(ValueError, "ENCODING"):
            extract.extract_bytes(
                raw, content_type="text/html", filing_sha256=hashlib.sha256(raw).hexdigest(),
                issuer_cik=CIK, accession=ACC, source_uri=self.receipt["source_uri"],
                input_origin="OFFLINE_FILE_UNVERIFIED",
            )

    def test_no_parser_remote_io_or_script_execution(self):
        with patch("urllib.request.urlopen") as req:
            r = self.run_from_saved()
            self.assertEqual(r["block_count"], 3)
            req.assert_not_called()

    def test_invalid_digest_rejected_even_for_correct_html(self):
        with self.assertRaisesRegex(ValueError, "DIGEST_MISMATCH"):
            extract.extract_bytes(
                RAW, content_type="text/html", filing_sha256="f" * 64,
                issuer_cik=CIK, accession=ACC, source_uri=self.receipt["source_uri"],
                input_origin="SEC_HTTPS_RESPONSE_UNVERIFIED"
            )

    def test_sqlite_tamper_detection_before_extract(self):
        with _sqlite_connection(self.db) as db:
            db.execute(
                "UPDATE original_filing_receipts SET file_bytes=? "
                "WHERE issuer_cik=? AND accession=? AND sha256=?",
                (b"CORRUPTED", CIK, ACC, self.saved["filing_sha256"]),
            )
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.run_from_saved()

    def test_unsupported_encodings_and_content_types_fail_closed(self):
        for raw, kind, origin, reason in (
            (b"\xff\xfe\x80", "text/html", "SEC_HTTPS_RESPONSE_UNVERIFIED", "ENCODING"),
            (RAW, "application/pdf", "SEC_HTTPS_RESPONSE_UNVERIFIED", "CONTENT_TYPE"),
            (RAW, "application/octet-stream", "SEC_HTTPS_RESPONSE_UNVERIFIED", "OPAQUE"),
        ):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                extract.extract_bytes(
                    raw, content_type=kind, filing_sha256=hashlib.sha256(raw).hexdigest(),
                    issuer_cik=CIK, accession=ACC, source_uri=self.receipt["source_uri"],
                    input_origin=origin,
                )

    def test_long_fragment_is_explicit_truncation(self):
        content = b"<html><body><p>" + (b"A" * 1800) + b"</p><p>GOOD</p></body></html>"
        receipt = extract.extract_bytes(
            content, content_type="text/html",
            filing_sha256=hashlib.sha256(content).hexdigest(),
            issuer_cik=CIK, accession=ACC, source_uri=self.receipt["source_uri"],
            input_origin="SEC_HTTPS_RESPONSE_UNVERIFIED",
        )
        self.assertTrue(receipt["truncated"])
        self.assertFalse(receipt["complete_text_extracted"])
        self.assertEqual([b["text"] for b in receipt["blocks"]], ["GOOD"])

    def test_malformed_hidden_blocks_do_not_claim_full_extraction(self):
        raw = b"<html><body>VISIBLE<script>INCOMPLETE"
        r = extract.extract_bytes(
            raw, content_type="text/html", filing_sha256=hashlib.sha256(raw).hexdigest(),
            issuer_cik=CIK, accession=ACC, source_uri=self.receipt["source_uri"],
            input_origin="SEC_HTTPS_RESPONSE_UNVERIFIED"
        )
        self.assertTrue(r["truncated"])
        self.assertEqual(r["blocks"][0]["text"], "VISIBLE")

    def test_excessive_hidden_nesting_is_bounded_and_fails_closed(self):
        depth = extract.MAX_HIDDEN_NESTING + 1
        raw = (b"<template>" * depth + b"HIDDEN" + b"</template>" * depth
               + b"<p>TAIL</p>")
        r = extract.extract_bytes(
            raw, content_type="text/html", filing_sha256=hashlib.sha256(raw).hexdigest(),
            issuer_cik=CIK, accession=ACC, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED",
        )
        self.assertTrue(r["truncated"])
        self.assertFalse(r["complete_text_extracted"])
        self.assertEqual(r["blocks"], [])

    def test_html_ignores_self_closing_slash_on_hidden_non_void_tags(self):
        raw = b"<script/>SECRET</script><p>VISIBLE</p><svg/>SVG-LABEL"
        html_result = extract.extract_bytes(
            raw, content_type="text/html", filing_sha256=hashlib.sha256(raw).hexdigest(),
            issuer_cik=CIK, accession=ACC, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED",
        )
        self.assertEqual([block["text"] for block in html_result["blocks"]],
                         ["VISIBLE", "SVG-LABEL"])

        xhtml = b"<script/>VISIBLE</script>"
        xml_result = extract.extract_bytes(
            xhtml, content_type="application/xhtml+xml",
            filing_sha256=hashlib.sha256(xhtml).hexdigest(), issuer_cik=CIK,
            accession=ACC, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED",
        )
        self.assertEqual([block["text"] for block in xml_result["blocks"]], ["VISIBLE"])

    def test_html_skips_embedded_and_media_fallback_text(self):
        raw = (
            b"<iframe>FRAME FALLBACK</iframe><object>OBJECT FALLBACK</object>"
            b"<canvas>CANVAS FALLBACK</canvas><video>VIDEO FALLBACK</video>"
            b"<p>VISIBLE BODY</p>"
        )
        receipt = extract.extract_bytes(
            raw, content_type="text/html", filing_sha256=hashlib.sha256(raw).hexdigest(),
            issuer_cik=CIK, accession=ACC, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED",
        )
        self.assertEqual([block["text"] for block in receipt["blocks"]], ["VISIBLE BODY"])

    def test_missing_or_wrong_saved_digest_fails(self):
        with self.assertRaises(ValueError):
            extract.from_saved_original(
                db_path=self.db, cik=CIK, accession=ACC, sha256="0" * 64)

    def test_as_of_extraction_excludes_original_bytes_added_after_cutoff(self):
        with _sqlite_connection(self.db) as db:
            db.execute(
                "UPDATE original_filing_receipts SET retrieved_at=? WHERE issuer_cik=? AND accession=?",
                ("2025-11-02T00:00:00Z", CIK, ACC),
            )
        args = {
            "db_path": self.db, "cik": CIK, "accession": ACC,
            "sha256": self.saved["filing_sha256"],
        }
        with self.assertRaisesRegex(ValueError, "NOT_FOUND_OR_AMBIGUOUS"):
            extract.from_saved_original(**args, as_of="2025-11-01")
        result = extract.from_saved_original(**args, as_of="2025-11-02")
        self.assertEqual(result["as_of"], "2025-11-02")
        self.assertEqual(result["block_count"], 3)

    def test_cli_summary_only_never_echoes_private_source_text(self):
        argv = [
            "--db", str(self.db), "--cik", CIK, "--accession", ACC,
            "--sha256", self.saved["filing_sha256"], "--as-of", "2099-12-31",
            "--summary-only"
        ]
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(extract.main(argv), 0)
        report = json.loads(stdout.getvalue())
        self.assertNotIn("blocks", report)
        self.assertNotIn("Revenue", stdout.getvalue())
        self.assertEqual(report["block_count"], 3)
        self.assertEqual(report["as_of"], "2099-12-31")

    def test_bounded_keyword_candidates_keep_source_line_and_digest(self):
        receipt = self.run_from_saved()
        found = extract.find_evidence_candidates(receipt, term="revenue")
        self.assertEqual(found["returned"], 1)
        self.assertEqual(found["filing_sha256"], receipt["filing_sha256"])
        self.assertEqual(found["candidates"][0]["text"], "2025 Revenue & Expenses")
        self.assertEqual(found["candidates"][0]["citation_status"],
                         "SOURCE_LINE_HINT_NEEDS_REVIEW")
        self.assertFalse(found["candidates"][0]["financial_claim_verified"])
        self.assertFalse(found["source_authenticity_verified"])

    def test_literal_html_candidate_keeps_exact_span_but_still_requires_review(self):
        receipt = self.run_from_saved()
        found = extract.find_evidence_candidates(receipt, term="Visible filing section")
        candidate = found["candidates"][0]
        self.assertEqual(candidate["citation_status"], "SOURCE_BYTE_SPAN_NEEDS_REVIEW")
        locator = candidate["source_locator"]
        self.assertEqual(locator["type"], "UTF8_HTML_TEXT_NODE_BYTE_SPAN")
        span = RAW[locator["start_byte"]:locator["end_byte_exclusive"]]
        self.assertEqual(span.decode("utf-8"), candidate["text"])
        self.assertEqual(candidate["raw_span_sha256"], hashlib.sha256(span).hexdigest())
        self.assertFalse(candidate["financial_claim_verified"])
        self.assertFalse(found["source_authenticity_verified"])

    def test_keyword_search_rejects_invalid_limits_and_empty_terms(self):
        receipt = self.run_from_saved()
        for term in ("", " ", "R", "Z" * 81, "Bad\nX"):
            with self.subTest(term=term), self.assertRaises(ValueError):
                extract.find_evidence_candidates(receipt, term=term)
        for limit in (-1, 0, 51, True):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                extract.find_evidence_candidates(receipt, term="Revenue",
                                                 max_results=limit)

    def test_cli_find_returns_candidates_without_claim_verification(self):
        argv = [
            "--db", str(self.db), "--cik", CIK, "--accession", ACC,
            "--sha256", self.saved["filing_sha256"], "--as-of", "2099-12-31",
            "--find", "revenue"
        ]
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(extract.main(argv), 0)
        got = json.loads(stdout.getvalue())
        self.assertEqual(got["schema"], "disclosure-lightning.evidence-candidates.v1")
        self.assertEqual(got["returned"], 1)
        self.assertEqual(got["as_of"], "2099-12-31")
        self.assertFalse(got["financial_claim_verified"])
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(extract.main(argv + ["--summary-only"]), 2)
        self.assertIn("cannot be combined", stderr.getvalue())

    def test_read_only_extraction_does_not_modify_sqlite_bytes(self):
        before = self.db.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(extract.main([
                "--db", str(self.db), "--cik", CIK, "--accession", ACC,
                "--sha256", self.saved["filing_sha256"],
                "--as-of", "2099-12-31", "--find", "revenue",
            ]), 0)
        self.assertEqual(self.db.read_bytes(), before)

    def test_same_raw_bytes_produce_deterministic_receipts(self):
        a = self.run_from_saved()
        b = self.run_from_saved()
        self.assertEqual(a, b)

    def test_opacity_of_html_in_offline_unknown_content_type(self):
        r = extract.extract_bytes(
            RAW, content_type="application/octet-stream",
            filing_sha256=hashlib.sha256(RAW).hexdigest(), issuer_cik=CIK,
            accession=ACC, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED"
        )
        self.assertEqual(r["extraction_method"], "utf8-lines")
        self.assertFalse(r["source_authenticity_verified"])


if __name__ == "__main__":
    unittest.main()
