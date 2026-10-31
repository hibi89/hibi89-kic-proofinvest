"""KUODRA bounded SEC transport to Guard audit; ALL HTTP calls mocked."""
from __future__ import annotations
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import sqlite3
import tempfile
import unittest

from proofinvest import kuodra_sec_guard as unit
from proofinvest import sec_three_source as capture
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.kic_dl_demo import (
    synthetic_submissions, synthetic_companyfacts, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
)
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML

_FIXED = datetime(2025, 10, 16, 12, 0, tzinfo=timezone.utc)
_CONTACT = "KUODRA researcher reachable@real-reviewer.org"


class _Response:
    status = 200

    def __init__(self, url: str, raw: bytes):
        self.url, self.raw = url, raw
        self.headers = {"Content-Type": "application/json",
                        "Content-Length": str(len(raw))}

    def geturl(self):
        return self.url

    def read(self, size):
        return self.raw[:size]

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        return None


class _Opener:
    def __init__(self, content):
        self.content = content

    def open(self, request, timeout):
        return _Response(request.full_url, self.content)


class KuodraSecGuardTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "guard.sqlite"
        self.kwargs = dict(
            cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
            current_end="2025-09-30", prior_end="2024-09-30",
            audit_db=self.db, run_id="unit-001",
            user_agent=_CONTACT, allow_network=True,
            acknowledge_three_requests=True,
            acknowledge_local_audit_persistence=True,
        )

    def _call_mock_transport(self, **changes):
        raw = json.dumps(synthetic_companyfacts()).encode()
        with (patch.object(capture, "_utcnow", return_value=_FIXED),
              patch.object(capture.time, "sleep"),
              patch.object(capture, "fetch_submissions",
                           return_value=synthetic_submissions()) as submissions,
              patch.object(capture, "fetch_original",
                           return_value=(SYNTHETIC_HTML, "text/html")) as original,
              patch.object(capture.urllib.request, "build_opener",
                           return_value=_Opener(raw)) as opener):
            result = unit.run_kuodra_sec_guard(**(self.kwargs | changes))
        return result, (submissions.call_count, original.call_count, opener.call_count)

    def test_no_consent_denies_all_network_and_db(self):
        for removed in ("allow_network", "acknowledge_three_requests",
                        "acknowledge_local_audit_persistence"):
            with self.subTest(removed=removed):
                with patch.object(unit, "run_sec_three_source_review",
                                  side_effect=AssertionError("NO HTTP")) as sec:
                    result = unit.run_kuodra_sec_guard(
                        **(self.kwargs | {removed: False}))
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["http_requests_attempted"], 0)
                self.assertFalse(self.db.exists())
                sec.assert_not_called()

    def test_actual_adapter_three_mocked_gets_to_sqlite_guard(self):
        result, calls = self._call_mock_transport()
        self.assertEqual(calls, (1, 1, 1))
        self.assertEqual(result["status"], "REVIEW_RECORDED_SOURCE_UNVERIFIED")
        self.assertEqual(result["http_requests_attempted"], 3)
        self.assertEqual(result["verification"]["growth_pct"], "100.00")
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertTrue(result["audit_written"])
        self.assertTrue(result["audit_chain_valid"])
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["trade_executed"])
        self.assertNotIn(_CONTACT, json.dumps(result))

    def test_numeric_conflict_rejected_in_same_flow(self):
        result, calls = self._call_mock_transport(claimed_growth_pct="300.00")
        self.assertEqual(calls, (1, 1, 1))
        self.assertEqual(result["verification"]["status"], "conflict")
        self.assertEqual(result["guard"]["decision"], "REJECT")
        self.assertFalse(result["guard"]["human_approved"])

    def test_postwrite_chain_verification_failure_does_not_claim_no_audit(self):
        # GuardAuditStore.verify_chain is also used by record_decision.
        # Patch the *independent post-commit* human-review verifier only,
        # so this test exercises a genuinely persisted-but-not-cleared case.
        with patch.object(unit.GuardReviewStore, "verify_reviews", return_value=False):
            result, calls = self._call_mock_transport()
        self.assertEqual(calls, (1, 1, 1))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason_code"], "AUDIT_INTEGRITY_OR_GUARD_FAILURE")
        self.assertIsNone(result["audit_written"])
        # A genuine local audit row was inserted before verify_chain failed.
        with closing(sqlite3.connect(self.db)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM guard_audit_events").fetchone()[0]
        self.assertEqual(count, 1)
        self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_write_then_exception_preserves_unknown_audit_state(self):
        original = unit.run_guard_review

        def after_commit(*args, **kwargs):
            original(*args, **kwargs)
            raise sqlite3.OperationalError("simulated post-commit failure")

        with patch.object(unit, "run_guard_review", side_effect=after_commit):
            result, calls = self._call_mock_transport()
        self.assertEqual(calls, (1, 1, 1))
        self.assertEqual(result["reason_code"], "GUARD_AUDIT_WRITE_FAILED")
        self.assertIsNone(result["audit_written"])
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM guard_audit_events"
            ).fetchone()[0], 1)

    def test_prewrite_consent_and_failed_transport_are_proven_false(self):
        with patch.object(unit, "run_sec_three_source_review",
                          side_effect=AssertionError("NO_HTTP")) as remote:
            denied = unit.run_kuodra_sec_guard(
                **(self.kwargs | {"acknowledge_local_audit_persistence": False}))
        self.assertIs(denied["audit_written"], False)
        remote.assert_not_called()
        self.assertFalse(self.db.exists())
        with patch.object(unit, "run_sec_three_source_review", return_value={
            "status": "unavailable", "http_requests_attempted": 2,
        }):
            fail = unit.run_kuodra_sec_guard(**self.kwargs)
        self.assertIs(fail["audit_written"], False)
        self.assertFalse(self.db.exists())

    def test_duplicate_run_prevents_second_sec_contact(self):
        self._call_mock_transport()
        with patch.object(unit, "run_sec_three_source_review",
                          side_effect=AssertionError("MUST_NOT_REFETCH")) as sec:
            res = unit.run_kuodra_sec_guard(**self.kwargs)
        self.assertEqual(res["reason_code"], "RUN_ID_ALREADY_USED_NO_REFETCH")
        sec.assert_not_called()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM guard_audit_events"
            ).fetchone()[0], 1)

    def test_tampered_audit_blocks_before_remote_requests(self):
        self._call_mock_transport()
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE guard_audit_events SET event_hash=?", ("0" * 64,))
        with patch.object(unit, "run_sec_three_source_review",
                          side_effect=AssertionError("NO HTTP")) as sec:
            result = unit.run_kuodra_sec_guard(
                **(self.kwargs | {"run_id": "unit-002"}))
        self.assertEqual(result["reason_code"], "AUDIT_DB_INTEGRITY_FAILURE")
        sec.assert_not_called()

    def test_existing_unrelated_db_not_modified(self):
        self.db.write_bytes(b"not a SQLite database")
        initial = self.db.read_bytes()
        with patch.object(unit, "run_sec_three_source_review",
                          side_effect=AssertionError("NO HTTP")) as sec:
            res = unit.run_kuodra_sec_guard(**self.kwargs)
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(self.db.read_bytes(), initial)
        sec.assert_not_called()

    def test_invalid_metadata_prevents_remote_requests(self):
        for changes in ({"run_id": "spaces fail"}, {"cik": "0000000000"},
                        {"accession": "malformed"}):
            with self.subTest(changes=changes):
                with patch.object(unit, "run_sec_three_source_review",
                                  side_effect=AssertionError("NO HTTP")) as sec:
                    res = unit.run_kuodra_sec_guard(**(self.kwargs | changes))
                self.assertEqual(res["http_requests_attempted"], 0)
                self.assertFalse(self.db.exists())
                sec.assert_not_called()

    def test_failed_transport_cannot_write_a_guard_receipt(self):
        with patch.object(unit, "run_sec_three_source_review", return_value={
            "schema": "proofinvest.sec-3source-explicit-transport.v1",
            "status": "unavailable",
            "http_requests_attempted": 2,
            "live_sec_http_called": True,
        }):
            res = unit.run_kuodra_sec_guard(**self.kwargs)
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(res["http_requests_attempted"], 2)
        self.assertFalse(self.db.exists())

    def test_cli_without_consent_is_offline_blocked(self):
        from proofinvest.kuodra_sec_guard import main
        with patch.object(unit, "run_sec_three_source_review",
                          side_effect=AssertionError("NO HTTP")):
            # Call via function and verify no network flags bypassed by CLI.
            with patch("sys.stdout") as output:
                code = main([
                    "--cik", SYNTHETIC_CIK, "--accession", SYNTHETIC_ACCESSION,
                    "--current-end", "2025-09-30", "--prior-end", "2024-09-30",
                    "--run-id", "cli-deny", "--audit-db", str(self.db)
                ])
            self.assertEqual(code, 2)
        self.assertFalse(self.db.exists())


if __name__ == "__main__":
    unittest.main()
