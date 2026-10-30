"""Offline SQLite audit tests; no external provider access."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from proofinvest.guard_agent import evaluate_guard
from proofinvest.guard_audit import GuardAuditStore


class GuardAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "audit.db"
        self.store = GuardAuditStore(self.path)
        self.request = {"source_kind": "SYNTHETIC_FIXTURE", "claim": "10"}
        self.decision = evaluate_guard(
            [{"status": "VERIFIED", "source_kind": "SYNTHETIC_FIXTURE"}],
            policy={"mode": "DEMO_POLICY", "version": "1", "max_debt_to_equity_pct": "200"},
            risk={"risk_calculated": True, "comparison_ratio_pct": "150"},
        )

    def test_write_and_replay(self):
        first = self.store.record_decision("demo-1", self.request, self.decision)
        second = self.store.record_decision("demo-1", self.request, self.decision)
        self.assertEqual(first["event_hash"], second["event_hash"])
        self.assertFalse(first["replayed"])
        self.assertTrue(second["replayed"])
        self.assertTrue(self.store.verify_chain())

    def test_different_payload_rejected(self):
        self.store.record_decision("demo-1", self.request, self.decision)
        with self.assertRaises(ValueError):
            self.store.record_decision("demo-1", {"claim": "changed"}, self.decision)

    def test_tamper_detected(self):
        self.store.record_decision("demo-1", self.request, self.decision)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("UPDATE guard_audit_events SET payload_json='{}'")
        self.assertFalse(self.store.verify_chain())
        with self.assertRaises(ValueError):
            self.store.record_decision("demo-2", self.request, self.decision)

    def test_malformed_nested_decision_fails_closed(self):
        import json
        from proofinvest.guard_audit import _canonical, _digest
        self.store.record_decision("demo-1", self.request, self.decision)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            payload = json.loads(conn.execute(
                "SELECT payload_json FROM guard_audit_events WHERE run_id='demo-1'"
            ).fetchone()[0])
            payload["decision"] = "malformed"
            encoded = _canonical(payload).decode("utf-8")
            digest = _digest("0" * 64, encoded.encode("utf-8"))
            conn.execute(
                "UPDATE guard_audit_events SET payload_json=?, event_hash=? WHERE run_id='demo-1'",
                (encoded, digest),
            )
            conn.execute(
                "UPDATE guard_run_registry SET decision=? WHERE run_id='demo-1'",
                (encoded,),
            )
        self.assertFalse(self.store.verify_chain())

    def test_blob_payload_fails_closed_without_exception(self):
        self.store.record_decision("demo-1", self.request, self.decision)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute(
                "UPDATE guard_audit_events SET payload_json=? WHERE run_id=?",
                (sqlite3.Binary(b"invalid-binary-payload"), "demo-1"),
            )
        self.assertFalse(self.store.verify_chain())
        with self.assertRaises(ValueError):
            self.store.record_decision("demo-2", self.request, self.decision)

    def test_blob_hash_fails_closed_without_exception(self):
        self.store.record_decision("demo-1", self.request, self.decision)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute(
                "UPDATE guard_audit_events SET event_hash=? WHERE run_id=?",
                (sqlite3.Binary(b"corrupt-hash"), "demo-1"),
            )
        self.assertFalse(self.store.verify_chain())
        with self.assertRaises(ValueError):
            self.store.record_decision("demo-2", self.request, self.decision)

    def test_invalid_run_id(self):
        with self.assertRaises(ValueError):
            self.store.record_decision("../escape", self.request, self.decision)

    def test_no_executed_decisions(self):
        with self.assertRaises(ValueError):
            self.store.record_decision("demo-1", self.request, {**self.decision, "trade_executed": True})

    def test_second_run_chain(self):
        self.store.record_decision("demo-1", self.request, self.decision)
        self.store.record_decision("demo-2", self.request, self.decision)
        self.assertTrue(self.store.verify_chain())


if __name__ == "__main__":
    unittest.main()
