"""Disclosure Lightning immutable metadata versions: synthetic SEC-shaped bytes."""
from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from disclosure_lightning import core

ROOT = Path(__file__).resolve().parents[1]
RAW = (ROOT / "disclosure_lightning" / "fixtures" /
       "sec_submissions_synthetic.json").read_bytes()
CIK = "0000320193"
AS_OF = "2026-10-27"
TIME = "2026-10-27T00:00:00Z"
ACCESSION = "0000320193-25-000901"


def indexed(raw: bytes) -> dict:
    return core.index_submissions(
        raw, cik=CIK, as_of=AS_OF,
        forms=core.parse_forms("10-K,10-K/A,8-K"),
        collected_at=TIME,
    )


def revised_input(*, change_filename: bool = True) -> bytes:
    changed = json.loads(RAW)
    changed["name"] = "SYNTHETIC DIFFERENT JSON SNAPSHOT"
    if change_filename:
        changed["filings"]["recent"]["primaryDocument"][0] = "new-revised-link.htm"
    return json.dumps(changed, sort_keys=True).encode("utf-8")


class DlVersionHistoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="dl-versions-")
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "filings.sqlite3"

    def test_metadata_change_creates_new_version_without_rewriting_first_seen(self):
        first = core.save_index(self.db, RAW, indexed(RAW))
        self.assertEqual(first["new_filings"], 3)
        self.assertEqual(first["new_metadata_versions"], 3)
        original = next(x for x in core.list_filings(self.db, cik=CIK)
                        if x["accession"] == ACCESSION)
        newraw = revised_input()
        changed = core.save_index(self.db, newraw, indexed(newraw))
        self.assertEqual(changed["new_filings"], 0)
        self.assertEqual(changed["new_metadata_versions"], 1)
        self.assertEqual(next(x for x in core.list_filings(self.db, cik=CIK)
                              if x["accession"] == ACCESSION), original)
        history = core.list_filing_versions(self.db, cik=CIK, accession=ACCESSION)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["metadata"]["source_uri"], original["source_uri"])
        self.assertIn("new-revised-link.htm", history[1]["metadata"]["source_uri"])
        self.assertNotEqual(history[0]["metadata_sha256"], history[1]["metadata_sha256"])
        self.assertEqual([x["observed_in_snapshots"] for x in history], [1, 1])
        self.assertTrue(all(not x["original_filing_downloaded"] for x in history))

    def test_same_source_reimport_and_json_only_change_do_not_create_new_version(self):
        first = core.save_index(self.db, RAW, indexed(RAW))
        second = core.save_index(self.db, RAW, indexed(RAW))
        self.assertEqual(second["new_metadata_versions"], 0)
        newraw = revised_input(change_filename=False)
        outcome = core.save_index(self.db, newraw, indexed(newraw))
        self.assertEqual(outcome["new_metadata_versions"], 0)
        versions = core.list_filing_versions(self.db, cik=CIK, accession=ACCESSION)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["observed_in_snapshots"], 2)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM observations").fetchone()[0], 2)

    def test_existing_sqlite_without_version_tables_migrates_in_place(self):
        core.save_index(self.db, RAW, indexed(RAW))
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("DROP TABLE filing_version_observations")
            conn.execute("DROP TABLE filing_metadata_versions")
        newraw = revised_input()
        core.save_index(self.db, newraw, indexed(newraw))
        versions = core.list_filing_versions(self.db, cik=CIK, accession=ACCESSION)
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]["first_submissions_sha256"],
                         indexed(RAW)["source_sha256"])
        self.assertEqual(versions[1]["first_submissions_sha256"],
                         indexed(newraw)["source_sha256"])

    def test_different_amendment_accession_does_not_merge_into_original(self):
        core.save_index(self.db, RAW, indexed(RAW))
        amended = core.list_filing_versions(
            self.db, cik=CIK, accession="0000320193-25-000902")
        self.assertEqual(len(amended), 1)
        self.assertEqual(amended[0]["metadata"]["form"], "10-K/A")
        self.assertIsNone(amended[0]["metadata"]["amends_accession"])
        self.assertEqual(
            len(core.list_filing_versions(self.db, cik=CIK, accession=ACCESSION)), 1)

    def test_cli_read_only_history_is_json_and_no_write(self):
        core.save_index(self.db, RAW, indexed(RAW))
        before = self.db.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            status = core.main(["--cik", CIK, "--as-of", AS_OF,
                                "--db", str(self.db),
                                "--history-accession", ACCESSION])
        self.assertEqual(status, 0)
        receipt = json.loads(out.getvalue())
        self.assertEqual(receipt["status"], "READ_ONLY_METADATA_HISTORY")
        self.assertEqual(len(receipt["versions"]), 1)
        self.assertEqual(before, self.db.read_bytes())
        with self.assertRaisesRegex(ValueError, "Invalid accession"):
            core.list_filing_versions(self.db, cik=CIK, accession="../bad")

    def test_original_content_sha_is_not_inferred_from_snapshot_sha(self):
        core.save_index(self.db, RAW, indexed(RAW))
        versions = core.list_filing_versions(self.db, cik=CIK, accession=ACCESSION)
        self.assertIsNone(versions[0]["metadata"]["raw_sha256"])
        self.assertNotEqual(versions[0]["first_submissions_sha256"], "")
        self.assertFalse(versions[0]["original_filing_downloaded"])


if __name__ == "__main__":
    unittest.main()
