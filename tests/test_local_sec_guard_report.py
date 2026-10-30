"""Offline local SEC evidence -> verification/risk/Guard/SQLite/report E2E."""
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.guard_review import GuardReviewStore
from proofinvest.local_sec_guard_report import review_local_sec_with_guard


def fixture(db: Path) -> dict:
    return {
        "submissions_json": synthetic_submissions(),
        "companyfacts_json": json.dumps(synthetic_companyfacts()).encode(),
        "original_filing": SYNTHETIC_HTML,
        "cik": SYNTHETIC_CIK,
        "accession": SYNTHETIC_ACCESSION,
        "as_of": AS_OF,
        "collected_at": COLLECTED_AT,
        "current_end": "2025-09-30",
        "prior_end": "2024-09-30",
        "needle": PHRASE,
        "claimed_growth_pct": "100.00",
        "audit_db_path": db,
        "run_id": "offline-one",
    }


class LocalSecGuardReportTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="kic-local-e2e-")
        self.addCleanup(self.folder.cleanup)
        self.db = Path(self.folder.name) / "audit.sqlite"

    def test_complete_three_file_path_holds_and_audits(self):
        result = review_local_sec_with_guard(**fixture(self.db))
        self.assertEqual(result["verification"]["status"], "calculated_unverified")
        self.assertEqual(result["verification"]["revenue_concept"],
                         "RevenueFromContractWithCustomerExcludingAssessedTax")
        self.assertEqual(result["verification"]["annual_period_starts"],
                         ["2023-10-01", "2024-10-01"])
        self.assertEqual(result["source"]["html_text_node_status"],
                         "untrusted_html_text_node_literal_located")
        self.assertEqual(result["risk"]["status"], "reviewed_unverified")
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertIn("RISK_UNAVAILABLE", result["guard"]["reason_codes"])
        self.assertTrue(result["audit_chain_valid"])
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertTrue(all(value is False for value in result["limits"].values()))
        self.assertNotIn(PHRASE, json.dumps(result))

    def test_changed_growth_claim_rejected_and_source_remains_unverified(self):
        args = fixture(self.db)
        args["claimed_growth_pct"] = "300.00"
        result = review_local_sec_with_guard(**args)
        self.assertEqual(result["verification"]["status"], "conflict")
        self.assertEqual(result["guard"]["decision"], "REJECT")
        self.assertFalse(result["limits"]["external_source_authenticated"])

    def test_script_only_phrase_cannot_be_reported_as_body_evidence(self):
        args = fixture(self.db)
        args["original_filing"] = (
            b"<html><script>" + PHRASE.encode() + b"</script><body>Other text</body></html>"
        )
        result = review_local_sec_with_guard(**args)
        self.assertEqual(result["source"]["html_text_node_status"], "unavailable")
        self.assertFalse(result["source"]["exact_raw_byte_span_verified"])
        self.assertEqual(result["guard"]["decision"], "HOLD")

    def test_replay_is_idempotent_and_source_change_is_blocked(self):
        args = fixture(self.db)
        first = review_local_sec_with_guard(**args)
        second = review_local_sec_with_guard(**args)
        self.assertFalse(first["audit"]["replayed"])
        self.assertTrue(second["audit"]["replayed"])
        with self.assertRaisesRegex(ValueError, "Run ID reused"):
            review_local_sec_with_guard(**(args | {
                "original_filing": args["original_filing"] + b" "
            }))
        with closing(sqlite3.connect(self.db)) as conn, conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM guard_audit_events").fetchone()[0], 1
            )

    def test_explicit_acknowledgement_keeps_no_authorization(self):
        args = fixture(self.db) | {
            "reviewer": "synthetic-reviewer",
            "action": "ACKNOWLEDGE",
            "reason": "Read the source limitations and verified the local audit",
        }
        result = review_local_sec_with_guard(**args)
        self.assertEqual(result["human_review"]["action"], "ACKNOWLEDGE")
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertTrue(GuardReviewStore(self.db).verify_reviews())
        self.assertFalse(result["limits"]["simulation_authorized"])

    def test_bad_action_rejected_before_db_write(self):
        with self.assertRaises(ValueError):
            review_local_sec_with_guard(**(fixture(self.db) | {
                "reviewer": "reviewer", "action": "AUTHORIZE_SIMULATION",
                "reason": "Attempted unauthorized simulated action",
            }))
        self.assertFalse(self.db.exists())

    def test_partial_review_rejected_before_db_write(self):
        with self.assertRaises(ValueError):
            review_local_sec_with_guard(**(fixture(self.db) | {
                "reviewer": "reviewer", "action": "ACKNOWLEDGE",
                "reason": "bad",
            }))
        self.assertFalse(self.db.exists())

    def test_bad_cik_and_invalid_local_input_leave_no_audit(self):
        with self.assertRaises(ValueError):
            review_local_sec_with_guard(**(fixture(self.db) | {"cik": "0000000002"}))
        self.assertFalse(self.db.exists())

    def test_symlink_database_is_not_written(self):
        existing = Path(self.folder.name) / "original.sqlite"
        existing.write_bytes(b"existing-user-file")
        alias = Path(self.folder.name) / "alias.sqlite"
        try:
            alias.symlink_to(existing)
        except OSError:
            self.skipTest("symlink unsupported")
        with self.assertRaises(ValueError):
            review_local_sec_with_guard(**(fixture(alias)))
        self.assertEqual(existing.read_bytes(), b"existing-user-file")

    def test_cli_opt_in_preserves_db_and_replay_receipt(self):
        """Exercise actual Python module CLI and existing SQLite, not a mock."""
        base = fixture(self.db)
        paths = {}
        for key in ("submissions_json", "companyfacts_json", "original_filing"):
            src = Path(self.folder.name) / (key + ".input")
            src.write_bytes(base[key])
            paths[key] = src
        cmd = [
            sys.executable, "-B", "-m", "proofinvest.local_sec_guard_report",
            "--submissions-json", str(paths["submissions_json"]),
            "--companyfacts-json", str(paths["companyfacts_json"]),
            "--original-file", str(paths["original_filing"]),
            "--cik", base["cik"], "--accession", base["accession"],
            "--as-of", base["as_of"], "--collected-at", base["collected_at"],
            "--current-end", base["current_end"], "--prior-end", base["prior_end"],
            "--needle", base["needle"], "--claimed-growth-pct",
            base["claimed_growth_pct"], "--run-id", base["run_id"],
            "--audit-db", str(self.db),
        ]
        working_dir = Path(__file__).resolve().parents[1]
        denied = subprocess.run(cmd, cwd=working_dir, capture_output=True,
                                text=True, timeout=30, check=False)
        self.assertEqual(denied.returncode, 2)
        self.assertFalse(self.db.exists(), "No opt-in: no SQLite side effects")
        approved = cmd + ["--acknowledge-local-audit-persistence"]
        first = subprocess.run(approved, cwd=working_dir, capture_output=True,
                               text=True, timeout=30, check=False)
        self.assertEqual(first.returncode, 0, first.stderr[:300])
        receipt = json.loads(first.stdout)
        self.assertEqual(receipt["guard"]["decision"], "HOLD")
        self.assertEqual(receipt["verification"]["status"], "calculated_unverified")
        self.assertFalse(receipt["audit"]["replayed"])
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertNotIn(PHRASE, first.stdout)
        second = subprocess.run(approved, cwd=working_dir, capture_output=True,
                                text=True, timeout=30, check=False)
        self.assertEqual(second.returncode, 0, second.stderr[:300])
        self.assertTrue(json.loads(second.stdout)["audit"]["replayed"])
        with closing(sqlite3.connect(self.db)) as conn, conn:
            count = conn.execute("SELECT COUNT(*) FROM guard_audit_events").fetchone()[0]
        self.assertEqual(count, 1)

    def test_no_external_http_in_three_source_guard_path(self):
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_EXTERNAL_NETWORK")) as network:
            result = review_local_sec_with_guard(**fixture(self.db))
        network.assert_not_called()
        self.assertFalse(result["limits"]["live_api_called"])


if __name__ == "__main__":
    unittest.main()
