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
        self.assertEqual(r["source_locator_accuracy"], "LINE_HINT_ONLY_NO_RAW_BYTE_SPANS")
        self.assertTrue(all(not b["exact_raw_byte_range_verified"] for b in r["blocks"]))
        for block in r["blocks"]:
            self.assertGreater(block["source_locator"]["line"], 0)
            self.assertEqual(block["text_sha256"], hashlib.sha256(
                block["text"].encode()).hexdigest())
        self.assertFalse(any("SCRIPT" in b["text"] or "Hidden" in b["text"] for b in r["blocks"]))

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
        with sqlite3.connect(self.db) as db:
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

    def test_missing_or_wrong_saved_digest_fails(self):
        with self.assertRaises(ValueError):
            extract.from_saved_original(
                db_path=self.db, cik=CIK, accession=ACC, sha256="0" * 64)

    def test_cli_summary_only_never_echoes_private_source_text(self):
        argv = [
            "--db", str(self.db), "--cik", CIK, "--accession", ACC,
            "--sha256", self.saved["filing_sha256"], "--summary-only"
        ]
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(extract.main(argv), 0)
        report = json.loads(stdout.getvalue())
        self.assertNotIn("blocks", report)
        self.assertNotIn("Revenue", stdout.getvalue())
        self.assertEqual(report["block_count"], 3)

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
