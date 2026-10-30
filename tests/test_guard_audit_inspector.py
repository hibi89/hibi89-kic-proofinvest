"""Closed SQLite Guard evidence check without modifying existing audit rows."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.guard_audit_inspector import inspect_guard_snapshot, main
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML


class GuardAuditSnapshotInspectorTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix="kic-inspector-")
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "audit.sqlite"
        self.report = review_local_sec_with_guard(
            submissions_json=synthetic_submissions(),
            companyfacts_json=json.dumps(synthetic_companyfacts()).encode(),
            original_filing=SYNTHETIC_HTML, cik=SYNTHETIC_CIK,
            accession=SYNTHETIC_ACCESSION, as_of=AS_OF,
            collected_at=COLLECTED_AT, current_end="2025-09-30",
            prior_end="2024-09-30", needle=PHRASE,
            claimed_growth_pct="100.00", audit_db_path=self.path,
            run_id="offline-inspector",
            reviewer="demo-reviewer", action="ACKNOWLEDGE",
            reason="This is an unverified source and needs human review",
        )

    def test_closed_snapshot_readonly_and_reports_zero_external_trust(self):
        prior = self.path.read_bytes()
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NETWORK_FORBIDDEN")) as network:
            summary = inspect_guard_snapshot(self.path)
        network.assert_not_called()
        self.assertEqual(self.path.read_bytes(), prior)
        self.assertEqual(summary["database_sha256"],
                         hashlib.sha256(prior).hexdigest())
        self.assertEqual(summary["status"], "LOCAL_HASH_CHAIN_VALID")
        self.assertEqual(summary["audit_events"], 1)
        self.assertEqual(summary["human_reviews"], 1)
        self.assertEqual(summary["decisions"], {"HOLD": 1, "REJECT": 0, "APPROVE": 0})
        self.assertFalse(summary["database_authenticated"])
        self.assertFalse(summary["sec_issuer_authenticated"])
        self.assertFalse(summary["trade_executed"])
        self.assertFalse(summary["raw_record_content_exported"])

    def test_receipt_never_includes_review_text_or_local_paths(self):
        summary = inspect_guard_snapshot(self.path)
        dumped = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn(str(self.path), dumped)
        self.assertNotIn("demo-reviewer", dumped)
        self.assertNotIn("needs human review", dumped)
        self.assertNotIn("offline-inspector", dumped)
        self.assertNotIn("reason", dumped.lower())

    def test_rejects_tampered_decision_and_never_repairs_db(self):
        with sqlite3.connect(self.path) as con:
            con.execute(
                "UPDATE guard_audit_events SET event_hash=?",
                ("0" * 64,),
            )
        corrupted = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "AUDIT_SNAPSHOT_CHAIN_INVALID"):
            inspect_guard_snapshot(self.path)
        self.assertEqual(self.path.read_bytes(), corrupted)

    def test_rejects_nonclosed_sidecar_and_symlink(self):
        sidecar = Path(str(self.path) + "-wal")
        sidecar.write_bytes(b"uncheckpointed")
        with self.assertRaisesRegex(ValueError, "AUDIT_SNAPSHOT_NOT_CLOSED"):
            inspect_guard_snapshot(self.path)
        sidecar.unlink()
        link = self.path.parent / "link.sqlite"
        try:
            link.symlink_to(self.path)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unsupported")
        with self.assertRaisesRegex(ValueError, "INVALID_AUDIT_SNAPSHOT"):
            inspect_guard_snapshot(link)

    def test_rejects_oversized_and_missing_file(self):
        with self.assertRaises(ValueError):
            inspect_guard_snapshot(self.path.parent / "missing.sqlite")
        huge = self.path.parent / "huge.sqlite"
        with huge.open("wb") as f:
            f.truncate(8_000_001)
        with self.assertRaisesRegex(ValueError, "INVALID_AUDIT_SNAPSHOT"):
            inspect_guard_snapshot(huge)

    def test_cli_success_and_fail_closed(self):
        from contextlib import redirect_stdout
        from io import StringIO
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(main([str(self.path)]), 0)
        receipt = json.loads(out.getvalue())
        self.assertEqual(receipt["status"], "LOCAL_HASH_CHAIN_VALID")
        with self.assertRaises(SystemExit) as exc:
            main([str(self.path.parent / "missing.sqlite")])
        self.assertEqual(exc.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
