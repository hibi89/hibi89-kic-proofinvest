"""Synthetic-only Windows SQLite reader-close regression for Streamlit history."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from streamlit_app import _read_guard_history_rows


class GuardHistoryReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kic-guard-history-")
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "audit.sqlite"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "CREATE TABLE guard_audit_events ("
                "event_id INTEGER PRIMARY KEY, run_id TEXT, event_type TEXT, "
                "event_hash TEXT, created_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE guard_human_reviews ("
                "review_id INTEGER PRIMARY KEY, run_id TEXT, reviewer TEXT, "
                "action TEXT, reason TEXT, reviewed_at TEXT, record_hash TEXT)"
            )
            conn.executemany(
                "INSERT INTO guard_audit_events VALUES (?, ?, ?, ?, ?)",
                [(i, "synthetic", "decision", "hash", "UTC") for i in range(1, 56)],
            )
            conn.execute(
                "INSERT INTO guard_human_reviews VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1, "synthetic", "tester", "ACKNOWLEDGE", "not live", "UTC", "hash"),
            )

    def assert_releasable(self):
        new = self.db.with_name("renamed.sqlite")
        self.db.rename(new)
        new.rename(self.db)

    def test_recent_history_and_reviews_read_without_writes(self):
        before = self.db.read_bytes()
        rows, reviews = _read_guard_history_rows(self.db)
        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[0][0], 55)
        self.assertEqual(rows[-1][0], 6)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0][3], "ACKNOWLEDGE")
        self.assertEqual(self.db.read_bytes(), before)
        self.assert_releasable()

    def test_legacy_database_without_human_reviews_table(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("DROP TABLE guard_human_reviews")
        rows, reviews = _read_guard_history_rows(self.db)
        self.assertEqual(len(rows), 50)
        self.assertEqual(reviews, [])
        self.assert_releasable()

    def test_reader_releases_handle_on_malformed_schema(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("DROP TABLE guard_audit_events")
        with self.assertRaises(sqlite3.OperationalError):
            _read_guard_history_rows(self.db)
        self.assert_releasable()


if __name__ == "__main__":
    unittest.main()
