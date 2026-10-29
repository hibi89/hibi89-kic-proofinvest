"""Regression proof: archived evidence -> financial/risk review -> Guard -> audit.

All inputs are self-authored synthetic SEC-shaped bytes; all SQLite paths are
temporary. No live SEC, private archive, model inference or trades.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.archived_sec_guard_report import (
    main, render_archived_sec_guard_markdown, run_archived_sec_guard_report,
)
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.guard_review import GuardReviewStore
from proofinvest.kic_dl_demo import (
    synthetic_companyfacts, synthetic_submissions,
    SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
)
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML, PHRASE
from proofinvest.sec_capture_bundle import (
    save_local_capture_bundle, verify_local_capture_bundle,
)
from proofinvest.sec_bundle_replay import replay_local_capture


class ArchivedSECGuardReportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="kic-archive-audit-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.archive = self.folder / "existing-evidence.zip"
        self.audit = self.folder / "guard-audit.sqlite"
        raw = {
            "submissions": synthetic_submissions(),
            "companyfacts": json.dumps(synthetic_companyfacts()).encode("utf-8"),
            "original_filing": SYNTHETIC_HTML,
        }
        stamp = "2025-10-16T12:00:00+00:00"
        receipt = {
            "schema": "proofinvest.sec-3source-explicit-transport.v1",
            "status": "three_sec_https_responses_captured_unverified",
            "http_requests_attempted": 3,
            "live_sec_http_called": True,
            "issuer_cik": SYNTHETIC_CIK,
            "accession": SYNTHETIC_ACCESSION,
            "observed_utc_day": "2025-10-16",
            "submissions_observed_at_utc": stamp,
            "companyfacts_observed_at_utc": stamp,
            "original_observed_at_utc": stamp,
            "source_uris": {
                "submissions": f"https://data.sec.gov/submissions/CIK{SYNTHETIC_CIK}.json",
                "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SYNTHETIC_CIK}.json",
                "original_filing": "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/synthetic10k.htm",
            },
            "raw_response_sha256": {
                k: hashlib.sha256(v).hexdigest() for k, v in raw.items()
            },
            "source_authenticated": False,
            "financial_facts_authenticated": False,
            "source_rights_verified": False,
            "official_contest_submission": False,
        }
        save_local_capture_bundle(self.archive, receipt=receipt, **raw)

    def report(self, **changes):
        kwargs = {
            "bundle_path": self.archive,
            "audit_db_path": self.audit,
            "current_end": "2025-09-30",
            "prior_end": "2024-09-30",
            "needle": PHRASE,
            "run_id": "kic-archive-one",
        }
        kwargs.update(changes)
        return run_archived_sec_guard_report(**kwargs)

    def test_full_backend_flow_research_finance_risk_guard_sqlite_report(self):
        before = self.archive.read_bytes()
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("UNAUTHORIZED_EXTERNAL_NETWORK")) as http:
            result = self.report()
        http.assert_not_called()
        self.assertEqual(before, self.archive.read_bytes())
        self.assertEqual(result["research"]["status"], "offline_local_metadata_only")
        self.assertEqual(result["verification"]["status"], "calculated_unverified")
        self.assertEqual(result["verification"]["growth_pct_recalculated_unverified"], "100.00")
        self.assertEqual(result["risk"]["status"], "reviewed_unverified")
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertTrue(result["audit"]["chain_valid"])
        self.assertTrue(result["audit"]["human_review_integrity_valid"])
        self.assertEqual(result["evidence"]["original_filing_sha256"],
                         hashlib.sha256(SYNTHETIC_HTML).hexdigest())
        self.assertEqual(result["review_summary"]["status"], "human_review_required")
        for key in ("live_api_called", "trade_executed", "source_authenticated",
                    "financial_values_authenticated", "investment_recommendation",
                    "official_contest_submission", "model_trained"):
            self.assertIs(result[key], False, key)
        self.assertTrue(GuardAuditStore(self.audit).verify_chain())
        self.assertTrue(GuardReviewStore(self.audit).verify_reviews())
        with sqlite3.connect(self.audit) as db:
            row = db.execute("SELECT payload_json FROM guard_audit_events").fetchone()[0]
            self.assertEqual(db.execute(
                "SELECT count(*) FROM guard_run_registry").fetchone()[0], 1)
        self.assertNotIn(PHRASE, row)
        self.assertNotIn("synthetic10k.htm", row)
        self.assertNotIn(str(self.archive), row)
        self.assertNotIn(PHRASE, json.dumps(result))

    def test_conflicting_financial_claim_escalates_to_reject_not_trade(self):
        result = self.report(claimed_growth_pct="1.00")
        self.assertEqual(result["verification"]["status"], "conflict")
        self.assertEqual(result["risk"]["status"], "unavailable")
        self.assertEqual(result["guard"]["decision"], "REJECT")
        self.assertIn("CLAIM_CONFLICT", result["guard"]["reason_codes"])
        self.assertEqual(result["review_summary"]["review_priority"], "high")
        self.assertFalse(result["trade_executed"])
        self.assertFalse(result["guard"]["human_approved"])

    def test_idempotent_same_run_and_pinned_evidence(self):
        first = self.report()
        second = self.report()
        self.assertFalse(first["audit"]["replayed"])
        self.assertTrue(second["audit"]["replayed"])
        self.assertEqual(first["audit"]["event_hash"], second["audit"]["event_hash"])
        self.assertEqual(first["evidence"]["evidence_chain_sha256"],
                         second["evidence"]["evidence_chain_sha256"])
        with sqlite3.connect(self.audit) as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM guard_audit_events").fetchone()[0], 1)

    def test_idempotency_key_cannot_refer_to_changed_claim(self):
        self.report(claimed_growth_pct="100.00")
        with self.assertRaisesRegex(ValueError, "Run ID reused"):
            self.report(claimed_growth_pct="100.01")
        self.assertTrue(GuardAuditStore(self.audit).verify_chain())
        with sqlite3.connect(self.audit) as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM guard_audit_events").fetchone()[0], 1)

    def test_corrupt_archive_blocks_audit_creation(self):
        raw = bytearray(self.archive.read_bytes())
        pos = raw.find(SYNTHETIC_HTML)
        self.assertGreater(pos, 0)
        raw[pos + 4] ^= 1
        self.archive.write_bytes(raw)
        self.assertEqual(verify_local_capture_bundle(self.archive)["status"], "unavailable")
        with self.assertRaisesRegex(ValueError, "REPLAY_NOT_REVIEWABLE"):
            self.report()
        self.assertFalse(self.audit.exists())

    def test_missing_original_span_and_bad_periods_block_without_audit(self):
        for opts in ({"needle": "NONEXISTENT_LITERAL"},
                     {"current_end": "2023-09-30"}):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                self.report(**opts)
            self.assertFalse(self.audit.exists())

    def test_invalid_review_and_simulation_authorization_are_write_free(self):
        for changes in (
            {"reviewer": "reviewer"},
            {"reviewer": "reviewer", "action": "AUTHORIZE_SIMULATION",
             "reason": "Cannot authorize on locally untrusted evidence"},
            {"reviewer": "reviewer", "action": "ACKNOWLEDGE", "reason": "bad"},
            {"reviewer": "", "action": "ACKNOWLEDGE", "reason": "Review only"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.report(**changes)
            self.assertFalse(self.audit.exists())

    def test_explicit_human_acknowledgement_does_not_override_guard(self):
        r = self.report(reviewer="reviewer-1", action="ACKNOWLEDGE",
                        reason="Unverified local synthetic receipt needs follow up")
        self.assertEqual(r["human_review"]["action"], "ACKNOWLEDGE")
        self.assertEqual(r["guard"]["decision"], "HOLD")
        self.assertFalse(r["human_review"]["trade_executed"])
        self.assertTrue(GuardReviewStore(self.audit).verify_reviews())

    def test_conflicting_claim_exception_request_remains_reject(self):
        r = self.report(claimed_growth_pct="1.00", reviewer="reviewer-2",
                        action="REQUEST_EXCEPTION", reason="Investigate conflict manually")
        self.assertEqual(r["guard"]["decision"], "REJECT")
        self.assertEqual(r["human_review"]["action"], "REQUEST_EXCEPTION")
        self.assertFalse(r["human_review"]["trade_executed"])

    def test_same_audit_db_as_zip_rejected_without_modifying_zip(self):
        data = self.archive.read_bytes()
        with self.assertRaises(ValueError):
            self.report(audit_db_path=self.archive)
        self.assertEqual(self.archive.read_bytes(), data)

    def test_invalid_run_id_or_symlink_db_rejected_before_archive_replay(self):
        with self.assertRaises(ValueError):
            self.report(run_id="a/b")
        self.assertFalse(self.audit.exists())
        target = self.folder / "elsewhere.db"
        target.write_text("not SQLite")
        self.audit.symlink_to(target)
        with self.assertRaises(ValueError):
            self.report()
        self.assertEqual(target.read_text(), "not SQLite")

    def test_tampered_existing_audit_does_not_accept_new_event(self):
        self.report()
        with sqlite3.connect(self.audit) as db:
            db.execute("UPDATE guard_audit_events SET payload_json='{}'")
        with self.assertRaises(ValueError):
            self.report(run_id="another")
        with sqlite3.connect(self.audit) as db:
            self.assertEqual(db.execute(
                "SELECT count(*) FROM guard_audit_events").fetchone()[0], 1)

    def test_forged_replay_attestation_does_not_write(self):
        original = replay_local_capture(
            self.archive, current_end="2025-09-30",
            prior_end="2024-09-30", needle=PHRASE,
        )
        for key in ("source_authenticated", "financial_values_authenticated",
                    "source_rights_verified", "external_http_called",
                    "official_contest_submission"):
            with self.subTest(key=key):
                changed = dict(original, **{key: True})
                with patch("proofinvest.archived_sec_guard_report.replay_local_capture",
                           return_value=changed), self.assertRaises(ValueError):
                    self.report()
                self.assertFalse(self.audit.exists())

    def test_mismatched_summary_or_source_hash_refused(self):
        original = replay_local_capture(
            self.archive, current_end="2025-09-30",
            prior_end="2024-09-30", needle=PHRASE,
        )
        tampered = copy.deepcopy(original)
        tampered["review_summary"]["financial_status"] = "conflict"
        with patch("proofinvest.archived_sec_guard_report.replay_local_capture",
                   return_value=tampered), self.assertRaises(ValueError):
            self.report()
        tampered = copy.deepcopy(original)
        tampered["local_integrity"]["sha256"]["original_filing"] = "0" * 64
        with patch("proofinvest.archived_sec_guard_report.replay_local_capture",
                   return_value=tampered), self.assertRaises(ValueError):
            self.report()
        self.assertFalse(self.audit.exists())

    def test_markdown_is_bounded_and_avoids_untrusted_html(self):
        result = self.report()
        markdown = render_archived_sec_guard_markdown(result)
        self.assertIn("**HOLD**", markdown)
        self.assertIn(result["evidence"]["evidence_chain_sha256"], markdown)
        self.assertNotIn(PHRASE, markdown)
        self.assertNotIn("<script>", markdown)
        self.assertNotIn(str(self.archive), markdown)
        with self.assertRaises(ValueError):
            render_archived_sec_guard_markdown({**result, "trade_executed": True})
        with self.assertRaises(ValueError):
            render_archived_sec_guard_markdown({
                **result, "guard": {**result["guard"], "decision": "APPROVE"}
            })

    def test_cli_json_and_markdown_are_safe(self):
        for fmt in ("json", "markdown"):
            with self.subTest(fmt=fmt):
                output, errors = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    rc = main([
                        "--bundle", str(self.archive), "--audit-db", str(self.audit),
                        "--current-end", "2025-09-30", "--prior-end", "2024-09-30",
                        "--needle", PHRASE, "--run-id", "one-cli", "--format", fmt,
                    ])
                self.assertEqual(rc, 0)
                self.assertEqual(errors.getvalue(), "")
                self.assertNotIn(PHRASE, output.getvalue())
                if fmt == "json":
                    self.assertEqual(json.loads(output.getvalue())["guard"]["decision"], "HOLD")
                else:
                    self.assertIn("**HOLD**", output.getvalue())

    def test_cli_invalid_local_input_redacts_path_and_does_not_write(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main([
                "--bundle", str(self.archive), "--audit-db", str(self.audit),
                "--current-end", "2025-09-30", "--prior-end", "2024-09-30",
                "--needle", "NONEXISTENT_LITERAL", "--run-id", "failed-cli",
            ])
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("SEC_ARCHIVE_AUDIT_FAILED", err.getvalue())
        self.assertNotIn(str(self.archive), err.getvalue())
        self.assertFalse(self.audit.exists())


if __name__ == "__main__":
    unittest.main()
