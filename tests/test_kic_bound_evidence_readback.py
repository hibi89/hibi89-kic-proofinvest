"""Read-back evidence binding regressions for the offline Guard report.

All files are self-authored synthetic test inputs. No SEC HTTP / trading.
"""
from __future__ import annotations

from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from proofinvest.archived_sec_guard_report import (
    render_archived_sec_guard_markdown,
    run_archived_sec_guard_report,
)
from proofinvest.guard_audit import GuardAuditStore, _canonical, _digest
from proofinvest.guard_bound_audit import verify_bound_guard_audit
from proofinvest.guard_review import GuardReviewStore
from proofinvest.kic_dl_original_demo import PHRASE
from proofinvest.sec_capture_bundle import save_local_capture_bundle
from tests.test_sec_bundle_replay import fixture


class BoundEvidenceReadbackTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="kic-guard-binding-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.archive = self.folder / "synthetic-sec.zip"
        self.database = self.folder / "guard.sqlite"
        receipt, sources = fixture()
        save_local_capture_bundle(self.archive, receipt=receipt, **sources)

    def report(self, *, claim=None, reviewer=None, action=None, reason=None):
        return run_archived_sec_guard_report(
            bundle_path=self.archive,
            audit_db_path=self.database,
            current_end="2025-09-30",
            prior_end="2024-09-30",
            needle=PHRASE,
            claimed_growth_pct=claim,
            run_id="evidence-run",
            reviewer=reviewer,
            action=action,
            reason=reason,
        )

    def verify(self, result, **changes):
        risk = result["risk"]
        kwargs = {
            "run_id": result["audit"]["run_id"],
            "source_evidence_digest": result["evidence"]["evidence_chain_sha256"],
            "financial_status": result["verification"]["status"],
            "risk_evidence": {
                "risk_calculated": False,
                "status": risk["status"],
                "reason_codes": risk["reason_codes"],
                "source_authenticated": False,
                "financial_values_authenticated": False,
                "source_rights_verified": False,
            },
            "event_id": result["audit"]["event_id"],
            "event_hash": result["audit"]["event_hash"],
            "guard_decision": result["guard"],
            "human_review": result["human_review"],
        }
        kwargs.update(changes)
        return verify_bound_guard_audit(self.database, **kwargs)

    def test_hold_run_bound_to_persisted_sources_risk_and_guard(self):
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NETWORK_FORBIDDEN")) as network:
            report = self.report()
            receipt = self.verify(report)
        network.assert_not_called()
        self.assertTrue(receipt["verified_against_persisted_request"])
        self.assertTrue(receipt["audit_chain_valid"])
        self.assertTrue(receipt["human_review_chain_valid"])
        self.assertEqual(receipt["guard_decision"], "HOLD")
        self.assertEqual(receipt["source_evidence_digest"],
                         report["evidence"]["evidence_chain_sha256"])
        self.assertEqual(report["audit"]["bound_source_evidence_sha256"],
                         report["evidence"]["evidence_chain_sha256"])
        self.assertTrue(report["audit"]["verified_against_persisted_request"])
        self.assertIn("cross-check: PASS", render_archived_sec_guard_markdown(report))
        self.assertIn("SOURCE_ORIGIN_UNAUTHENTICATED", report["risk"]["reason_codes"])
        self.assertTrue(GuardAuditStore(self.database).verify_chain())

    def test_conflict_run_remains_reject_and_bound(self):
        report = self.report(claim="1.00")
        self.assertEqual(report["guard"]["decision"], "REJECT")
        self.assertEqual(report["risk"]["status"], "unavailable")
        self.assertIn("CLAIMED_GROWTH_CONFLICT", report["risk"]["reason_codes"])
        self.assertEqual(self.verify(report)["guard_decision"], "REJECT")

    def test_same_id_exact_replay_has_identical_persisted_binding(self):
        one, two = self.report(), self.report()
        self.assertTrue(two["audit"]["replayed"])
        self.assertEqual(one["audit"]["event_hash"], two["audit"]["event_hash"])
        self.assertEqual(one["audit"]["bound_source_evidence_sha256"],
                         two["audit"]["bound_source_evidence_sha256"])
        self.assertTrue(self.verify(two)["verified_against_persisted_request"])

    def test_wrong_source_hash_risk_status_or_guard_fails_readback(self):
        result = self.report()
        changes = [
            {"source_evidence_digest": "0" * 64},
            {"financial_status": "conflict"},
            {"risk_evidence": {**{
                "risk_calculated": False, "status": result["risk"]["status"],
                "reason_codes": result["risk"]["reason_codes"],
                "source_authenticated": False,
                "financial_values_authenticated": False,
                "source_rights_verified": False,
            }, "status": "unavailable"}},
            {"event_id": result["audit"]["event_id"] + 1},
            {"event_hash": "f" * 64},
            {"guard_decision": {**result["guard"], "decision": "APPROVE"}},
        ]
        for delta in changes:
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                self.verify(result, **delta)
        self.assertTrue(GuardAuditStore(self.database).verify_chain())

    def test_rehashed_forgery_passes_basic_chain_but_fails_evidence_binding(self):
        result = self.report()
        with closing(sqlite3.connect(self.database)) as db, db:
            row = db.execute(
                "SELECT payload_json FROM guard_audit_events WHERE event_id=?",
                (result["audit"]["event_id"],),
            ).fetchone()
            altered = json.loads(row[0])
            altered["request_hash"] = "f" * 64
            payload = _canonical(altered).decode("utf-8")
            digest = _digest("0" * 64, payload.encode("utf-8"))
            db.execute(
                "UPDATE guard_audit_events SET payload_json=?, event_hash=? WHERE event_id=?",
                (payload, digest, result["audit"]["event_id"]),
            )
            db.execute(
                "UPDATE guard_run_registry SET request_hash=?, decision=? WHERE run_id=?",
                ("f" * 64, payload, result["audit"]["run_id"]),
            )
        # Basic internal hash chain has been coherently rewritten by a
        # privileged local editor; the independently recomputed source binding
        # still detects that the payload does NOT match current input.
        self.assertTrue(GuardAuditStore(self.database).verify_chain())
        with self.assertRaisesRegex(ValueError, "STORED_GUARD_NOT_BOUND"):
            self.verify(result)
        self.assertFalse(GuardAuditStore(self.database).verify_chain() is False)

    def test_explicit_review_stays_bound_to_original_event(self):
        result = self.report(reviewer="reviewer-1", action="ACKNOWLEDGE",
                             reason="Local unverified source acknowledged")
        receipt = self.verify(result)
        self.assertEqual(receipt["review_id"], result["human_review"]["review_id"])
        self.assertTrue(GuardReviewStore(self.database).verify_reviews())
        bad = dict(result["human_review"], record_hash="0" * 64)
        with self.assertRaisesRegex(ValueError, "HUMAN_REVIEW_DOES_NOT_MATCH"):
            self.verify(result, human_review=bad)
        self.assertEqual(result["guard"]["decision"], "HOLD")

    def test_missing_db_does_not_create_file(self):
        report = self.report()
        empty = self.folder / "not-a-db.sqlite"
        with self.assertRaisesRegex(ValueError, "FILE_NOT_FOUND"):
            verify_bound_guard_audit(
                empty, run_id="evidence-run",
                source_evidence_digest=report["evidence"]["evidence_chain_sha256"],
                financial_status="calculated_unverified",
                risk_evidence={
                    "risk_calculated": False, "status": "reviewed_unverified",
                    "reason_codes": report["risk"]["reason_codes"],
                    "source_authenticated": False,
                    "financial_values_authenticated": False,
                    "source_rights_verified": False,
                },
                event_id=report["audit"]["event_id"],
                event_hash=report["audit"]["event_hash"],
                guard_decision=report["guard"],
            )
        self.assertFalse(empty.exists())

    def test_renderer_rejects_forged_evidence_binding(self):
        report = self.report()
        for forged in (
            {**report, "audit": {
                **report["audit"], "verified_against_persisted_request": False,
            }},
            {**report, "audit": {
                **report["audit"], "bound_source_evidence_sha256": "a" * 64,
            }},
            {**report, "audit": {
                **report["audit"], "bound_guard_decision": "APPROVE",
            }},
        ):
            with self.assertRaises(ValueError):
                render_archived_sec_guard_markdown(forged)


if __name__ == "__main__":
    unittest.main()
