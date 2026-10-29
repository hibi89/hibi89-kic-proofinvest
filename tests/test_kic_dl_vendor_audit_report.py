"""DL saved filing -> Guard HOLD -> SQLite audit -> report regressions."""
from __future__ import annotations

import sqlite3
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integrations.dl_vendor import core, originals
from proofinvest.dl_vendor_audit_report import (
    main, render_dl_audit_markdown, run_saved_dl_audit_report,
)
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.guard_review import GuardReviewStore
from proofinvest.guard_workflow import run_guard_review

CIK = "0000320193"
ACCESSION = "0000320193-25-000079"
DAY = "2025-11-01"
FIXTURE = (Path(__file__).resolve().parents[1] /
           "integrations/dl_vendor/fixtures/kic_apple_handoff_synthetic.json")


class DLSavedAuditReportTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="dl-guard-report-")
        self.addCleanup(folder.cleanup)
        self.source = Path(folder.name) / "dl.sqlite"
        self.audit = Path(folder.name) / "guard.sqlite"
        raw = FIXTURE.read_bytes()
        index = core.index_submissions(
            raw, cik=CIK, as_of=DAY, forms=core.parse_forms("10-K"),
            collected_at="2025-11-01T10:30:00Z",
            provenance="OFFLINE_UNVERIFIED",
        )
        core.save_index(self.source, raw, index)
        location = originals.locate_original(
            self.source, cik=CIK, accession=ACCESSION,
        )
        with patch("integrations.dl_vendor.originals._timestamp",
                   return_value="2025-11-01T10:32:00Z"):
            receipt = originals.persist_original(
                db_path=self.source, receipt=location,
                raw=(b"<html><p>Revenue 100</p>"
                     b"<script>NEVER ECHO</script></html>"),
                kind="text/html", origin="OFFLINE_FILE_UNVERIFIED",
            )
        self.sha = receipt["filing_sha256"]

    def run_report(self, **kwargs):
        arguments = dict(
            dl_db_path=self.source, audit_db_path=self.audit,
            cik=CIK, accession=ACCESSION, sha256=self.sha,
            as_of=DAY, term="Revenue", run_id="dl-one",
        )
        arguments.update(kwargs)
        return run_saved_dl_audit_report(**arguments)

    def test_end_to_end_guard_sqlite_audit_and_report(self):
        report = self.run_report()
        self.assertEqual(report["guard"]["decision"], "HOLD")
        self.assertEqual(report["evidence"]["candidate_count"], 1)
        self.assertTrue(report["audit"]["chain_valid"])
        self.assertTrue(report["audit"]["human_review_integrity_valid"])
        self.assertFalse(report["audit"]["replayed"])
        self.assertFalse(report["source"]["source_authenticated"])
        self.assertFalse(report["evidence"]["financial_claim_verified"])
        self.assertFalse(report["trade_executed"])
        self.assertIsNone(report["human_review"])
        self.assertEqual(report["source"]["filing_sha256"], self.sha)
        self.assertTrue(GuardAuditStore(self.audit).verify_chain())
        with sqlite3.connect(self.audit) as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM guard_run_registry").fetchone()[0], 1)
            audit_payload = conn.execute(
                "SELECT payload_json FROM guard_audit_events").fetchone()[0]
        self.assertNotIn("Revenue 100", audit_payload)
        self.assertNotIn("NEVER ECHO", str(report))

    def test_identical_replay_keeps_same_record(self):
        first = self.run_report()
        second = self.run_report()
        self.assertEqual(first["audit"]["event_hash"], second["audit"]["event_hash"])
        self.assertTrue(second["audit"]["replayed"])
        with sqlite3.connect(self.audit) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM guard_run_registry").fetchone()[0], 1)

    def test_same_run_changed_evidence_is_rejected(self):
        self.run_report()
        with self.assertRaisesRegex(ValueError, "Run ID reused"):
            self.run_report(term="Another")
        self.assertTrue(GuardAuditStore(self.audit).verify_chain())
        with sqlite3.connect(self.audit) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM guard_audit_events").fetchone()[0], 1)

    def test_invalid_source_never_creates_audit(self):
        with self.assertRaises(ValueError):
            self.run_report(sha256="a" * 64)
        self.assertFalse(self.audit.exists())
        with self.assertRaises(ValueError):
            self.run_report(as_of="2025-10-31")
        self.assertFalse(self.audit.exists())

    def test_invalid_or_implicit_human_review_does_not_write(self):
        for opts in (
            {"reviewer": "human"},
            {"reviewer": "human", "action": "AUTHORIZE_SIMULATION",
             "reason": "Not permitted on unverified source"},
            {"reviewer": "human", "action": "ACKNOWLEDGE", "reason": "bad"},
        ):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                self.run_report(**opts)
            self.assertFalse(self.audit.exists())

    def test_explicit_human_review_is_recorded_without_approval(self):
        report = self.run_report(
            reviewer="offline-human", action="ACKNOWLEDGE",
            reason="Acknowledge synthetic unverified source",
        )
        self.assertEqual(report["human_review"]["action"], "ACKNOWLEDGE")
        self.assertEqual(report["guard"]["decision"], "HOLD")
        self.assertFalse(report["human_review"]["trade_executed"])
        self.assertTrue(GuardReviewStore(self.audit).verify_reviews())

    def test_tampered_audit_fails_reuse(self):
        self.run_report()
        with sqlite3.connect(self.audit) as conn:
            conn.execute("UPDATE guard_audit_events SET payload_json='{}'")
        with self.assertRaises(ValueError):
            self.run_report(run_id="dl-two")

    def test_markdown_report_omits_filing_text(self):
        report = self.run_report()
        markdown = render_dl_audit_markdown(report)
        self.assertIn("**HOLD**", markdown)
        self.assertIn(self.sha, markdown)
        self.assertIn("not the official organizer PDF", markdown)
        self.assertNotIn("Revenue 100", markdown)
        self.assertNotIn("NEVER ECHO", markdown)
        with self.assertRaises(ValueError):
            render_dl_audit_markdown({**report, "trade_executed": True})

    def test_separate_db_required(self):
        with self.assertRaises(ValueError):
            self.run_report(audit_db_path=self.source)
        with self.assertRaises(ValueError):
            self.run_report(audit_db_path=self.source.parent)
        self.assertFalse(self.audit.exists())

    def cli(self, *, fmt="json", as_of=DAY):
        args = [
            "--dl-db", str(self.source), "--audit-db", str(self.audit),
            "--cik", CIK, "--accession", ACCESSION, "--sha256", self.sha,
            "--as-of", as_of, "--term", "Revenue", "--run-id", "cli-demo",
            "--format", fmt,
        ]
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main(args)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_cli_json_end_to_end(self):
        status, out, err = self.cli()
        self.assertEqual(status, 0)
        self.assertEqual(err, "")
        result = json.loads(out)
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertTrue(result["audit"]["chain_valid"])
        self.assertFalse(result["live_api_called"])

    def test_cli_markdown_omits_untrusted_text(self):
        status, out, err = self.cli(fmt="markdown")
        self.assertEqual(status, 0)
        self.assertEqual(err, "")
        self.assertIn("**HOLD**", out)
        self.assertNotIn("Revenue 100", out)
        self.assertNotIn("NEVER ECHO", out)

    def test_cli_fail_closed_does_not_create_audit(self):
        status, out, err = self.cli(as_of="2025-10-30")
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertIn("INVALID_LOCAL_INPUT_OR_EVIDENCE", err)
        self.assertNotIn(str(self.source), err)
        self.assertFalse(self.audit.exists())

    def test_invalid_evidence_fingerprint_precheck_is_write_free(self):
        with self.assertRaises(ValueError):
            run_guard_review(
                {"status": "unavailable"},
                run_id="bad-fingerprint", database_path=self.audit,
                source_evidence_digest="bad-hash",
            )
        self.assertFalse(self.audit.exists())


if __name__ == "__main__":
    unittest.main()
