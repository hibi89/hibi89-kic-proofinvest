"""Registry consistency regression for the offline Guard audit."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from proofinvest.guard_agent import evaluate_guard
from proofinvest.guard_audit import GuardAuditStore

class RegistryLinkContract(unittest.TestCase):
    def test_registry_request_hash_must_match_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.sqlite"
            store = GuardAuditStore(path)
            decision = evaluate_guard(
                [{"status": "VERIFIED", "source_kind": "SYNTHETIC_FIXTURE"}],
                policy={"mode": "DEMO_POLICY", "version": "1",
                        "max_debt_to_equity_pct": "200"},
                risk={"risk_calculated": True, "comparison_ratio_pct": "100"},
            )
            store.record_decision("one", {"claim": "original"}, decision)
            self.assertTrue(store.verify_chain())
            with sqlite3.connect(path) as conn:
                conn.execute("UPDATE guard_run_registry SET request_hash=? WHERE run_id=?",
                             ("0" * 64, "one"))
            self.assertFalse(store.verify_chain())

if __name__ == "__main__":
    unittest.main()
