"""Offline SQLite audit tests; no external provider access."""
import sqlite3
import tempfile
import unittest
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
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE guard_audit_events SET payload_json='{}'")
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
