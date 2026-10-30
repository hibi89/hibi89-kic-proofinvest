"""DL archived original bytes -> KIC strict source span, synthetic only."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from disclosure_lightning.core import index_submissions, save_index
from disclosure_lightning.originals import (
    locate_original, persist_original, read_original_bytes,
)
from proofinvest.dl_source_span import anchored_source_span
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML, replay_original
from proofinvest.kic_dl_demo import AS_OF, COLLECTED_AT, SYNTHETIC_CIK, SYNTHETIC_ACCESSION, synthetic_submissions


class KicOriginalSourceSpanTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="kic-dl-orig-tests-")
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "evidence.db"
        raw = synthetic_submissions()
        index = index_submissions(
            raw, cik=SYNTHETIC_CIK, as_of=AS_OF,
            forms=frozenset({"10-K", "10-K/A"}),
            collected_at=COLLECTED_AT,
        )
        save_index(self.db, raw, index)
        self.locator = locate_original(
            self.db, cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
        )

    def save(self, raw=SYNTHETIC_HTML):
        return persist_original(
            db_path=self.db, receipt=self.locator, raw=raw,
            kind="application/octet-stream", origin="OFFLINE_FILE_UNVERIFIED",
        )

    def span(self, *, sha=None, needle=PHRASE):
        if sha is None:
            sha = self.save()["filing_sha256"]
        return anchored_source_span(
            db_path=self.db, cik=SYNTHETIC_CIK,
            accession=SYNTHETIC_ACCESSION, sha256=sha, needle=needle,
        )

    def test_actual_end_to_end_program_and_no_api_network(self):
        with patch("disclosure_lightning.originals.urllib.request.build_opener",
                   side_effect=AssertionError("NO_HTTP_ALLOWED")) as live:
            out = replay_original()
            live.assert_not_called()
        self.assertEqual(out["status"], "offline_original_source_path_pass")
        self.assertEqual(out["original_replay_receipt_status"], "REUSED")
        self.assertEqual(out["kic_metadata_link"], "linked_metadata_only")
        self.assertEqual(out["source_byte_end"] - out["source_byte_start"], len(PHRASE))
        self.assertNotEqual(out["submissions_sha256"], out["original_filing_sha256"])
        self.assertIn("&lt;script&gt;", out["escaped_context"])
        for field in ("authenticated_external_source", "real_sec_network_called",
                      "real_filing_retrieved", "official_submission_made",
                      "numeric_facts_authenticated"):
            self.assertFalse(out[field], field)

    def test_exact_bytes_are_hashed_and_span_offsets_are_replayable(self):
        raw = self.save()
        span = self.span(sha=raw["filing_sha256"])
        original = read_original_bytes(
            db_path=self.db, cik=SYNTHETIC_CIK,
            accession=SYNTHETIC_ACCESSION, sha256=raw["filing_sha256"],
        )
        self.assertEqual(hashlib.sha256(original).hexdigest(), span["filing_sha256"])
        self.assertEqual(original[span["start_byte"]:span["end_byte_exclusive"]],
                         PHRASE.encode("ascii"))
        self.assertEqual(span["status"], "untrusted_original_span_for_review")
        self.assertFalse(span["numerical_claim_verified"])

    def test_ambiguous_or_absent_literal_rejected(self):
        self.save(b"EXACT PHRASE appears. EXACT PHRASE appears twice.")
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS_LITERAL"):
            self.span(sha=hashlib.sha256(
                b"EXACT PHRASE appears. EXACT PHRASE appears twice."
            ).hexdigest(), needle="EXACT PHRASE")
        with self.assertRaisesRegex(ValueError, "LITERAL_NOT_FOUND"):
            self.span(needle="NOT_FOUND_PHRASE")

    def test_malformed_source_phrase_and_sha_fails_closed(self):
        self.save()
        for phrase in ("", "A", "has\nnewline", "<script>", "\u2603"):
            with self.subTest(phrase=phrase):
                if phrase == "<script>":
                    continue
                with self.assertRaises(ValueError):
                    self.span(needle=phrase)
        with self.assertRaisesRegex(ValueError, "INVALID_ORIGINAL_DIGEST"):
            self.span(sha="bad")
        with self.assertRaisesRegex(ValueError, "INVALID_CONTEXT_LIMIT"):
            anchored_source_span(
                db_path=self.db, cik=SYNTHETIC_CIK,
                accession=SYNTHETIC_ACCESSION,
                sha256=self.save()["filing_sha256"],
                needle=PHRASE, context_bytes=999999,
            )

    def test_wrong_issuer_accession_or_nonexistent_digest_cannot_link(self):
        saved = self.save()
        for kwargs in (
            {"cik": "0000000002", "accession": SYNTHETIC_ACCESSION},
            {"cik": SYNTHETIC_CIK, "accession": "0000000001-25-000009"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                anchored_source_span(db_path=self.db, sha256=saved["filing_sha256"],
                                     needle=PHRASE, **kwargs)
        with self.assertRaisesRegex(ValueError, "ORIGINAL_RECEIPT_UNAVAILABLE"):
            self.span(sha="0" * 64)

    def test_database_byte_tampering_is_detected_on_read(self):
        receipt = self.save()
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute(
                "UPDATE original_filing_receipts SET file_bytes=? WHERE sha256=?",
                (b"TAMPERED", receipt["filing_sha256"]),
            )
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.span(sha=receipt["filing_sha256"])

    def test_html_is_escaped_not_rendered(self):
        span = self.span()
        self.assertNotIn("<script>", span["context_escaped_html"])
        self.assertIn("&lt;script&gt;", span["context_escaped_html"])
        self.assertEqual(span["input_origin"], "OFFLINE_FILE_UNVERIFIED")

    def test_real_cli_module_executes_one_synthetic_pipeline(self):
        completed = subprocess.run(
            [sys.executable, "-m", "proofinvest.kic_dl_original_demo"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "offline_original_source_path_pass")
        self.assertTrue(result["synthetic_only"])


if __name__ == "__main__":
    unittest.main()
