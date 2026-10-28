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


def _drop_observation_guards(db):
    for trigger in ("observations_no_update", "observations_no_delete",
                    "filings_no_update", "filings_no_delete"):
        db.execute(f"DROP TRIGGER IF EXISTS {trigger}")


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
        with _sqlite_connection(self.db) as db:
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
        with _sqlite_connection(self.db) as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM original_filing_receipts").fetchone()[0], 1)

    def test_original_receipts_and_http_checks_are_append_only(self):
        saved = self.save()
        digest = saved["filing_sha256"]
        with _sqlite_connection(self.db) as db:
            db.execute(
                "INSERT INTO original_http_checks VALUES(?,?,?,?,?,?)",
                (C, A, self.receipt["source_uri"], digest,
                 "2026-10-27T01:00:00Z", "SYNTHETIC_CHECK"),
            )
        mutations = (
            ("UPDATE original_filing_receipts SET retrieved_at='changed' WHERE sha256=?", (digest,)),
            ("DELETE FROM original_filing_receipts WHERE sha256=?", (digest,)),
            ("INSERT OR REPLACE INTO original_filing_receipts VALUES(?,?,?,?,?,?,?,?)",
             (C, A, digest, self.receipt["source_uri"], "changed",
              "OFFLINE_FILE_UNVERIFIED", "application/octet-stream", CONTENT)),
            ("UPDATE original_http_checks SET provenance='CHANGED' WHERE sha256=?", (digest,)),
            ("DELETE FROM original_http_checks WHERE sha256=?", (digest,)),
        )
        for sql, parameters in mutations:
            with self.subTest(sql=sql.split()[0:3]):
                with _sqlite_connection(self.db) as db, self.assertRaisesRegex(
                        sqlite3.IntegrityError, "append-only"):
                    db.execute(sql, parameters)
        with _sqlite_connection(self.db) as db:
            check = db.execute(
                "SELECT issuer_cik,accession,source_uri,sha256,checked_at,provenance "
                "FROM original_http_checks WHERE sha256=?", (digest,),
            ).fetchone()
            db.execute("INSERT OR REPLACE INTO original_http_checks VALUES(?,?,?,?,?,?)", check)
            self.assertEqual(db.execute(
                "SELECT count(*) FROM original_http_checks WHERE sha256=?", (digest,),
            ).fetchone()[0], 1)

    def test_simultaneous_original_replay_saves_one_receipt(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        start = Barrier(2)

        def save_after_start():
            start.wait(timeout=5)
            return self.save()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=10) for future in (
                pool.submit(save_after_start), pool.submit(save_after_start))]
        self.assertEqual(sorted(item["status"] for item in results), ["REUSED", "SAVED"])
        self.assertEqual({item["filing_sha256"] for item in results},
                         {hashlib.sha256(CONTENT).hexdigest()})
        with _sqlite_connection(self.db) as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM original_filing_receipts").fetchone()[0], 1)

    def test_failed_original_receipt_write_rolls_back_and_recovers(self):
        self.save()
        changed = b"<html>SECOND SYNTHETIC RECEIPT</html>"
        with _sqlite_connection(self.db) as db:
            db.execute(
                "CREATE TRIGGER reject_original_receipt BEFORE INSERT ON original_filing_receipts "
                "BEGIN SELECT RAISE(ABORT, 'synthetic receipt failure'); END",
            )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "synthetic receipt failure"):
            self.save(changed)
        with _sqlite_connection(self.db) as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM original_filing_receipts",
            ).fetchone()[0], 1)
            db.execute("DROP TRIGGER reject_original_receipt")
        retried = self.save(changed)
        self.assertEqual(retried["status"], "SAVED")
        with _sqlite_connection(self.db) as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM original_filing_receipts",
            ).fetchone()[0], 2)

    def test_changed_document_never_overwrites_prior_bytes(self):
        original = self.save()
        updated = self.save(b"<html>CHANGED SYNTHETIC</html>")
        self.assertEqual(updated["status"], "SAVED")
        self.assertNotEqual(updated["filing_sha256"], original["filing_sha256"])
        items = originals.list_originals(db_path=self.db, cik=C, accession=A)
        self.assertEqual({r["filing_sha256"] for r in items},
                         {original["filing_sha256"], updated["filing_sha256"]})
        with _sqlite_connection(self.db) as db:
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

    def test_cached_live_transport_requires_exact_persisted_locator(self):
        fabricated = {
            **self.receipt,
            "evidence_status": "INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED",
        }
        with patch("disclosure_lightning.originals.urllib.request.build_opener") as opener:
            with self.assertRaisesRegex(ValueError, "persisted indexed metadata"):
                originals.fetch_original_with_cache(
                    db_path=self.db, receipt=fabricated,
                    user_agent="DL Ops test@actualcorp.org", allow_network=True,
                )
            opener.assert_not_called()

    def test_mocked_sec_archive_download_saves_bytes_but_not_certification(self):
        from email.message import Message
        from urllib.error import HTTPError

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
            opener.return_value.open.side_effect = [
                HTTPError(receipt["source_uri"], 503, "Service Unavailable",
                         Message(), io.BytesIO(b"")),
                Response(),
            ]
            with patch("disclosure_lightning.core.time.sleep") as sleep:
                got, mime = originals.fetch_original(
                    receipt=receipt, user_agent="DL Ops admin@actualcorp.org",
                    allow_network=True,
                )
            self.assertEqual(got, CONTENT)
            self.assertEqual(mime, "text/html")
            self.assertEqual(opener.return_value.open.call_count, 2)
            sleep.assert_called_once_with(0.5)
        result = originals.persist_original(
            db_path=other_db, receipt=receipt, raw=got,
            kind=mime, origin="SEC_HTTPS_RESPONSE_UNVERIFIED",
        )
        self.assertEqual(result["status"], "SAVED")
        self.assertEqual(result["filing_sha256"], hashlib.sha256(CONTENT).hexdigest())
        self.assertTrue(result["original_filing_retrieved"])
        self.assertFalse(result["authenticated_external_source"])

    def test_archive_etag_304_reuses_only_integrity_checked_original_blob(self):
        from email.message import Message
        from urllib.error import HTTPError

        index = core.index_submissions(
            self.index_raw, cik=C, as_of="2026-10-27",
            forms=core.parse_forms("10-K"), provenance="SEC_HTTPS_RESPONSE",
            collected_at="2026-10-27T00:00:00Z",
        )
        self.db = self.root / "archive-official.db"
        core.save_index(self.db, self.index_raw, index)
        receipt = originals.locate_original(self.db, cik=C, accession=A)
        etag = 'W/"synthetic-archive-v1"'
        empty_304 = HTTPError(
            receipt["source_uri"], 304, "Not Modified", Message(), io.BytesIO(b""))
        with patch("disclosure_lightning.originals.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = empty_304
            with self.assertRaisesRegex(ValueError, "without a hash-verified cached original"):
                originals.fetch_original_with_cache(
                    db_path=self.db, receipt=receipt,
                    user_agent="DL Ops admin@actualcorp.org", allow_network=True,
                )

        class Response:
            status = 200
            headers = {"Content-Type": "text/html", "Content-Length": str(len(CONTENT)),
                       "ETag": etag}
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
            raw, kind, saved_etag, unchanged = originals.fetch_original_with_cache(
                db_path=self.db, receipt=receipt,
                user_agent="DL Ops admin@actualcorp.org", allow_network=True,
            )
            request = opener.return_value.open.call_args.args[0]
            self.assertIsNone(request.get_header("If-none-match"))
        self.assertEqual((raw, kind, saved_etag, unchanged),
                         (CONTENT, "text/html", etag, False))
        originals.persist_original(
            db_path=self.db, receipt=receipt, raw=raw, kind=kind,
            origin="SEC_HTTPS_RESPONSE_UNVERIFIED", etag=saved_etag,
        )

        headers = Message()
        headers["ETag"] = etag
        not_modified = HTTPError(
            receipt["source_uri"], 304, "Not Modified", headers, io.BytesIO(b""))
        with patch("disclosure_lightning.originals.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = not_modified
            reused, reused_kind, reused_etag, unchanged = originals.fetch_original_with_cache(
                db_path=self.db, receipt=receipt,
                user_agent="DL Ops admin@actualcorp.org", allow_network=True,
            )
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header("If-none-match"), etag)
        self.assertEqual((reused, reused_kind, reused_etag, unchanged),
                         (CONTENT, "text/html", etag, True))
        persisted = originals.persist_original(
            db_path=self.db, receipt=receipt, raw=reused, kind=reused_kind,
            origin="SEC_HTTPS_RESPONSE_UNVERIFIED", etag=reused_etag,
            http_not_modified=unchanged,
        )
        self.assertTrue(persisted["http_cache_response_not_modified"])
        with _sqlite_connection(self.db) as db:
            self.assertEqual(db.execute(
                "SELECT provenance FROM original_http_checks ORDER BY checked_at DESC LIMIT 1"
            ).fetchone()[0], "SEC_HTTPS_304_NOT_MODIFIED")
            db.execute("DROP TRIGGER IF EXISTS original_receipts_no_update")
            db.execute("UPDATE original_filing_receipts SET file_bytes=? WHERE sha256=?",
                       (b"tampered", hashlib.sha256(CONTENT).hexdigest()))
        with self.assertRaisesRegex(ValueError, "integrity validation"):
            originals._load_original_http_cache(self.db, receipt)

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

    def test_verified_read_only_original_bytes_for_kic_parser(self):
        saved = self.save()
        with self.assertRaisesRegex(ValueError, "not available by as-of"):
            originals.locate_original(
                self.db, cik=C, accession=A, as_of="2000-01-01")
        self.assertEqual(originals.locate_original(
            self.db, cik=C, accession=A, as_of="2099-12-31"), self.receipt)
        raw = originals.read_original_bytes(
            db_path=self.db, cik=C, accession=A,
            sha256=saved["filing_sha256"],
        )
        self.assertEqual(raw, CONTENT)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), saved["filing_sha256"])
        with self.assertRaisesRegex(ValueError, "not available by as-of"):
            originals.read_original_bytes(
                db_path=self.db, cik=C, accession=A,
                sha256=saved["filing_sha256"], as_of="2000-01-01")
        self.assertEqual(originals.read_original_bytes(
            db_path=self.db, cik=C, accession=A,
            sha256=saved["filing_sha256"], as_of="2099-12-31"), CONTENT)

    def test_as_of_receipt_lookup_includes_fractional_second_before_day_end(self):
        saved = self.save()
        with _sqlite_connection(self.db) as db:
            db.execute("DROP TRIGGER IF EXISTS original_receipts_no_update")
            db.execute("UPDATE original_filing_receipts SET retrieved_at=?",
                       ("2026-10-27T23:59:59.500000Z",))
        self.assertEqual(len(originals.list_originals(
            db_path=self.db, cik=C, accession=A, as_of="2026-10-27")), 1)
        self.assertEqual(originals.read_original_bytes(
            db_path=self.db, cik=C, accession=A,
            sha256=saved["filing_sha256"], as_of="2026-10-27"), CONTENT)
        for invalid in ("", "../secret", "G" * 64, "0" * 63):
            with self.subTest(sha=invalid), self.assertRaises(ValueError):
                originals.read_original_bytes(
                    db_path=self.db, cik=C, accession=A, sha256=invalid)
        with self.assertRaises(KeyError):
            originals.read_original_bytes(
                db_path=self.db, cik=C, accession=A, sha256="0" * 64)

    def test_as_of_receipt_listing_requires_index_observation_by_cutoff(self):
        saved = self.save()
        with _sqlite_connection(self.db) as db:
            _drop_observation_guards(db)
            db.execute("DROP TRIGGER IF EXISTS original_receipts_no_update")
            db.execute(
                "UPDATE observations SET seen_at=? WHERE issuer_cik=?",
                ("2026-10-28T00:00:00Z", C),
            )
            db.execute(
                "UPDATE original_filing_receipts SET retrieved_at=? WHERE sha256=?",
                ("2026-10-27T12:00:00Z", saved["filing_sha256"]),
            )
        self.assertEqual(originals.list_originals(
            db_path=self.db, cik=C, accession=A, as_of="2026-10-27"), [])

    def test_as_of_byte_read_uses_one_sqlite_snapshot(self):
        saved = self.save()
        with _sqlite_connection(self.db) as db:
            db.execute("DROP TRIGGER IF EXISTS original_receipts_no_update")
            db.execute(
                "UPDATE original_filing_receipts SET retrieved_at=? WHERE sha256=?",
                ("2026-10-27T12:00:00Z", saved["filing_sha256"]),
            )
        validator = originals._validate_locator_receipt

        def change_receipt_after_preflight(receipt, cik, accession):
            location = validator(receipt, cik, accession)
            with _sqlite_connection(self.db) as db:
                db.execute("DROP TRIGGER IF EXISTS original_receipts_no_update")
                db.execute(
                    "UPDATE original_filing_receipts SET retrieved_at=? WHERE sha256=?",
                    ("2026-10-28T00:00:00Z", saved["filing_sha256"]),
                )
            return location

        with patch.object(originals, "_validate_locator_receipt",
                          side_effect=change_receipt_after_preflight):
            self.assertEqual(originals.read_original_bytes(
                db_path=self.db, cik=C, accession=A,
                sha256=saved["filing_sha256"], as_of="2026-10-27"), CONTENT)

    def test_original_read_without_receipt_table_is_a_missing_receipt(self):
        blank = self.root / "blank.db"
        sqlite3.connect(blank).close()
        with self.assertRaisesRegex(KeyError, "receipt not found"):
            originals.read_original_bytes(
                db_path=blank, cik=C, accession=A, sha256="0" * 64)

    def test_original_locator_rechecks_saved_index_bytes_and_metadata(self):
        saved = self.save()
        with _sqlite_connection(self.db) as db:
            _drop_observation_guards(db)
            db.execute("UPDATE observations SET response=? WHERE issuer_cik=?",
                       (b"{}", C))
        with self.assertRaisesRegex(ValueError, "index source integrity"):
            originals.locate_original(self.db, cik=C, accession=A)
        with self.assertRaisesRegex(ValueError, "index source integrity"):
            originals.read_original_bytes(
                db_path=self.db, cik=C, accession=A,
                sha256=saved["filing_sha256"])

    def test_persist_rechecks_index_under_write_reservation(self):
        locator = originals.locate_original
        calls = 0

        def mutate_after_preflight(*args, **kwargs):
            nonlocal calls
            result = locator(*args, **kwargs)
            calls += 1
            if calls == 1:
                with _sqlite_connection(self.db) as db:
                    _drop_observation_guards(db)
                    db.execute("UPDATE observations SET response=? WHERE issuer_cik=?",
                               (b"{}", C))
            return result

        with patch.object(originals, "locate_original", side_effect=mutate_after_preflight):
            with self.assertRaisesRegex(ValueError, "index source integrity"):
                self.save()
        with _sqlite_connection(self.db) as db:
            self.assertIsNone(db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='original_filing_receipts'"
            ).fetchone())

    def test_original_listing_rejects_matching_but_tampered_locator_metadata(self):
        saved = self.save()
        tampered_uri = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000901/fake.htm"
        with _sqlite_connection(self.db) as db:
            _drop_observation_guards(db)
            record = json.loads(db.execute(
                "SELECT filing_json FROM filings WHERE accession=?", (A,)
            ).fetchone()[0])
            record["source_uri"] = tampered_uri
            db.execute("UPDATE filings SET filing_json=? WHERE accession=?",
                       (json.dumps(record), A))
            db.execute("DROP TRIGGER IF EXISTS original_receipts_no_update")
            db.execute("UPDATE original_filing_receipts SET source_uri=? WHERE sha256=?",
                       (tampered_uri, saved["filing_sha256"]))
        with self.assertRaisesRegex(ValueError, "metadata does not match"):
            originals.list_originals(db_path=self.db, cik=C, accession=A)

    def test_corrupted_original_blob_fails_closed_when_read(self):
        saved = self.save()
        with _sqlite_connection(self.db) as conn:
            conn.execute("DROP TRIGGER IF EXISTS original_receipts_no_update")
            conn.execute(
                "UPDATE original_filing_receipts SET file_bytes=? "
                "WHERE issuer_cik=? AND accession=? AND sha256=?",
                (b"CORRUPTED", C, A, saved["filing_sha256"]),
            )
        with self.assertRaisesRegex(ValueError, "integrity"):
            originals.read_original_bytes(
                db_path=self.db, cik=C, accession=A,
                sha256=saved["filing_sha256"])

    def test_original_receipt_must_remain_linked_to_indexed_source_uri(self):
        saved = self.save()
        with _sqlite_connection(self.db) as conn:
            conn.execute("DROP TRIGGER IF EXISTS original_receipts_no_update")
            conn.execute(
                "UPDATE original_filing_receipts SET source_uri=? "
                "WHERE issuer_cik=? AND accession=? AND sha256=?",
                ("https://attacker.invalid/fake.htm", C, A, saved["filing_sha256"]),
            )
        self.assertEqual(originals.list_originals(
            db_path=self.db, cik=C, accession=A), [])
        with self.assertRaisesRegex(ValueError, "source URI"):
            originals.read_original_bytes(
                db_path=self.db, cik=C, accession=A,
                sha256=saved["filing_sha256"])

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
            self.assertEqual(originals.main(args[:-2] + ["--list", "--as-of", "2000-01-01"]), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["as_of"], "2000-01-01")
        self.assertEqual(result["receipts"], [])
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(originals.main(args[:-2] + ["--list", "--as-of", "2099-12-31"]), 0)
        self.assertEqual(len(json.loads(out.getvalue())["receipts"]), 1)

    def test_offline_html_source_to_saved_text_evidence_e2e(self):
        from disclosure_lightning.extract import from_saved_original, find_evidence_candidates
        html = (
            b"<html><head><title>HIDDEN</title></head><body>"
            b"<h1>Synthetic filing heading</h1>"
            b"<script>UNSAFE SCRIPT</script>"
            b"<p>Synthetic Revenue &amp; evidence</p>"
            b"</body></html>"
        )
        source = self.root / "fake-source.html"
        source.write_bytes(html)
        argv = [
            "--db", str(self.db), "--cik", C, "--accession", A,
            "--input-file", str(source), "--content-type", "text/html",
        ]
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(originals.main(argv), 0)
        saved = json.loads(stdout.getvalue())
        self.assertEqual(saved["input_origin"], "OFFLINE_FILE_UNVERIFIED")
        self.assertFalse(saved["original_filing_retrieved"])
        self.assertEqual(saved["content_type"], "text/html")
        receipt = from_saved_original(
            db_path=self.db, cik=C, accession=A, sha256=saved["filing_sha256"]
        )
        self.assertEqual([r["text"] for r in receipt["blocks"]],
                         ["Synthetic filing heading", "Synthetic Revenue & evidence"])
        matches = find_evidence_candidates(receipt, term="Revenue")
        self.assertEqual(matches["returned"], 1)
        self.assertEqual(matches["candidates"][0]["citation_status"],
                         "SOURCE_LINE_HINT_NEEDS_REVIEW")
        self.assertFalse(matches["financial_claim_verified"])
        with contextlib.redirect_stdout(io.StringIO()) as again:
            self.assertEqual(originals.main(argv), 0)
        self.assertEqual(json.loads(again.getvalue())["status"], "REUSED")

    def test_live_mime_override_rejected_before_network_access(self):
        with patch("disclosure_lightning.originals.fetch_original") as fetch:
            with contextlib.redirect_stderr(io.StringIO()) as out:
                code = originals.main([
                    "--db", str(self.db), "--cik", C, "--accession", A,
                    "--allow-network", "--content-type", "text/html",
                ])
            self.assertEqual(code, 2)
            self.assertIn("Live content-type", out.getvalue())
            fetch.assert_not_called()

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
