"""DL full primary-document receipt tests. Synthetic and mocked HTTPS only."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from disclosure_lightning import core, originals

C = "0000320193"
A = "0000320193-25-000901"
FIXTURE = (Path(__file__).resolve().parents[1]
           / "disclosure_lightning/fixtures/sec_submissions_synthetic.json")
CONTENT = b"<html><head><title>OFFLINE SYNTHETIC</title></head><body>Not a SEC filing</body></html>"


class OriginalFilingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="dl-original-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / "index.db"
        self.index_raw = FIXTURE.read_bytes()
        index = core.index_submissions(
            self.index_raw, cik=C, as_of="2026-10-27",
            forms=core.parse_forms("10-K,10-K/A,8-K"),
            collected_at="2026-10-27T00:00:00Z",
        )
        core.save_index(self.db, self.index_raw, index)
        self.receipt = originals.locate_original(self.db, cik=C, accession=A)

    def save(self, raw=CONTENT, *, origin="OFFLINE_FILE_UNVERIFIED",
             kind="application/octet-stream"):
        return originals.persist_original(
            db_path=self.db, receipt=self.receipt,
            raw=raw, kind=kind, origin=origin,
        )

    def test_original_index_is_official_host_but_only_metadata_unverified(self):
        self.assertEqual(self.receipt["issuer_cik"], C)
        self.assertEqual(self.receipt["accession"], A)
        self.assertTrue(self.receipt["source_uri"].startswith(
            "https://www.sec.gov/Archives/edgar/data/320193/"))
        self.assertIsNone(self.receipt["raw_sha256"])
        self.assertEqual(self.receipt["evidence_status"], "OFFLINE_SOURCE_UNVERIFIED")

    def test_save_exact_filing_bytes_and_digest_without_changing_index(self):
        before = self.db.read_bytes()
        outcome = self.save()
        self.assertEqual(outcome["status"], "SAVED")
        self.assertEqual(outcome["filing_sha256"], hashlib.sha256(CONTENT).hexdigest())
        self.assertFalse(outcome["authenticated_external_source"])
        self.assertFalse(outcome["original_filing_retrieved"])
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute(
                "SELECT file_bytes FROM original_filing_receipts"
            ).fetchone()[0], CONTENT)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM filings").fetchone()[0], 3)
        self.assertNotEqual(before, self.db.read_bytes())
        self.assertEqual(originals.locate_original(self.db, cik=C, accession=A), self.receipt)

    def test_exact_replay_no_duplicate_receipt(self):
        first, second = self.save(), self.save()
        self.assertEqual((first["status"], second["status"]), ("SAVED", "REUSED"))
        self.assertEqual(originals.list_originals(
            db_path=self.db, cik=C, accession=A
        )[0]["filing_sha256"], first["filing_sha256"])
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM original_filing_receipts").fetchone()[0], 1)

    def test_changed_document_never_overwrites_prior_bytes(self):
        original = self.save()
        updated = self.save(b"<html>CHANGED SYNTHETIC</html>")
        self.assertEqual(updated["status"], "SAVED")
        self.assertNotEqual(updated["filing_sha256"], original["filing_sha256"])
        items = originals.list_originals(db_path=self.db, cik=C, accession=A)
        self.assertEqual({r["filing_sha256"] for r in items},
                         {original["filing_sha256"], updated["filing_sha256"]})
        with sqlite3.connect(self.db) as db:
            raws = {row[0] for row in db.execute(
                "SELECT file_bytes FROM original_filing_receipts")}
        self.assertEqual(raws, {CONTENT, b"<html>CHANGED SYNTHETIC</html>"})

    def test_missing_or_malicious_filing_identifier_never_fetches(self):
        for accession in ("", "../bad", "0000320193-25-000999", "0000320193-25-000901/"):
            with self.subTest(accession=accession), self.assertRaises(ValueError):
                originals.locate_original(self.db, cik=C, accession=accession)

    def test_invalid_original_payload_and_provenance_refused(self):
        before = self.db.read_bytes()
        for raw in (b"", b"a" * (originals.MAX_FILING_BYTES + 1)):
            with self.subTest(n=len(raw)), self.assertRaisesRegex(ValueError, "bytes"):
                self.save(raw)
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.save(origin="SEC_VERIFIED")
        self.assertEqual(before, self.db.read_bytes())

    def test_offline_file_symlink_refused(self):
        source = self.root / "safe.html"
        source.write_bytes(CONTENT)
        alias = self.root / "link.html"
        try:
            alias.symlink_to(source)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not supported")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            originals._read_local(alias)

    def test_network_requires_explicit_allow_and_real_agent(self):
        with patch("disclosure_lightning.originals.urllib.request.build_opener") as opener:
            with self.assertRaisesRegex(ValueError, "allow-network"):
                originals.fetch_original(
                    receipt=self.receipt, user_agent="", allow_network=False)
            with self.assertRaisesRegex(ValueError, "User-Agent"):
                originals.fetch_original(
                    receipt=self.receipt, user_agent="DL contact@example.com",
                    allow_network=True)
            with self.assertRaisesRegex(ValueError, "previously indexed SEC HTTPS"):
                originals.fetch_original(
                    receipt=self.receipt, user_agent="DL Ops test@actualcorp.org",
                    allow_network=True)
            opener.assert_not_called()

    def test_live_transport_never_fetches_arbitrary_url(self):
        bad = {**self.receipt,
               "evidence_status": "INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED",
               "source_uri": "https://evil.example/Archives/edgar/data/320193/bad.html"}
        with patch("disclosure_lightning.originals.urllib.request.build_opener") as opener:
            with self.assertRaisesRegex(ValueError, "URL"):
                originals.fetch_original(
                    receipt=bad, user_agent="DL Ops test@actualcorp.org",
                    allow_network=True)
            opener.assert_not_called()

    def test_mocked_sec_archive_download_saves_bytes_but_not_certification(self):
        index = core.index_submissions(
            self.index_raw, cik=C, as_of="2026-10-27",
            forms=core.parse_forms("10-K"), provenance="SEC_HTTPS_RESPONSE",
            collected_at="2026-10-27T00:00:00Z",
        )
        other_db = self.root / "official-shape.db"
        core.save_index(other_db, self.index_raw, index)
        receipt = originals.locate_original(other_db, cik=C, accession=A)

        class Response:
            status = 200
            headers = {"Content-Type": "text/html", "Content-Length": str(len(CONTENT))}
            def geturl(self):
                return receipt["source_uri"]
            def read(self, size):
                return CONTENT
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return None

        with patch("disclosure_lightning.originals.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = Response()
            got, mime = originals.fetch_original(
                receipt=receipt, user_agent="DL Ops admin@actualcorp.org",
                allow_network=True,
            )
            self.assertEqual(got, CONTENT)
            self.assertEqual(mime, "text/html")
            opener.return_value.open.assert_called_once()
        result = originals.persist_original(
            db_path=other_db, receipt=receipt, raw=got,
            kind=mime, origin="SEC_HTTPS_RESPONSE_UNVERIFIED",
        )
        self.assertEqual(result["status"], "SAVED")
        self.assertEqual(result["filing_sha256"], hashlib.sha256(CONTENT).hexdigest())
        self.assertTrue(result["original_filing_retrieved"])
        self.assertFalse(result["authenticated_external_source"])

    def test_mock_sec_wrong_media_type_redirect_and_size_refused(self):
        receipt = {**self.receipt,
                   "evidence_status": "INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED"}

        class Response:
            status = 200
            headers = {"Content-Type": "application/javascript"}
            def __init__(self, target):
                self.target = target
            def geturl(self):
                return self.target
            def read(self, size):
                return CONTENT
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return None

        with patch("disclosure_lightning.originals.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = Response(receipt["source_uri"])
            with self.assertRaisesRegex(ValueError, "content-type"):
                originals.fetch_original(
                    receipt=receipt, user_agent="DL Ops admin@actualcorp.org",
                    allow_network=True)
            bad = Response("https://evil.example/redirected")
            bad.headers = {"Content-Type": "text/html"}
            opener.return_value.open.return_value = bad
            with self.assertRaisesRegex(ValueError, "redirect"):
                originals.fetch_original(
                    receipt=receipt, user_agent="DL Ops admin@actualcorp.org",
                    allow_network=True)
            oversize = Response(receipt["source_uri"])
            oversize.headers = {"Content-Type": "text/html", "Content-Length": "25000001"}
            opener.return_value.open.return_value = oversize
            with self.assertRaisesRegex(ValueError, "size"):
                originals.fetch_original(
                    receipt=receipt, user_agent="DL Ops admin@actualcorp.org",
                    allow_network=True)

    def test_cli_offline_file_roundtrip_and_readonly_list(self):
        source = self.root / "synthetic-filing.html"
        source.write_bytes(CONTENT)
        args = [
            "--db", str(self.db), "--cik", C, "--accession", A,
            "--input-file", str(source),
        ]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(originals.main(args), 0)
        record = json.loads(out.getvalue())
        self.assertEqual(record["status"], "SAVED")
        self.assertEqual(record["input_origin"], "OFFLINE_FILE_UNVERIFIED")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(originals.main(args), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "REUSED")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(originals.main(args[:-2] + ["--list"]), 0)
        self.assertEqual(len(json.loads(out.getvalue())["receipts"]), 1)

    def test_module_subprocess_invocation_offline(self):
        source = self.root / "synthetic-filing.html"
        source.write_bytes(CONTENT)
        completed = subprocess.run([
            sys.executable, "-m", "disclosure_lightning.originals",
            "--db", str(self.db), "--cik", C, "--accession", A,
            "--input-file", str(source),
        ], capture_output=True, text=True, timeout=15,
           cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "SAVED")


if __name__ == "__main__":
    unittest.main()
