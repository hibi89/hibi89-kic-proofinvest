"""Explicit local human review for simulated Guard decisions only.

A human review never changes the Guard decision or triggers real transactions.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class GuardReviewStore:
    def __init__(self, path: str | Path):
        self.path = str(path)

    def record_review(self, run_id: str, reviewer: str, action: str, reason: str) -> dict:
        if action not in ("ACKNOWLEDGE", "REQUEST_EXCEPTION", "AUTHORIZE_SIMULATION"):
            raise ValueError("Unsupported review action")
        if not isinstance(reviewer, str) or not (1 <= len(reviewer.strip()) <= 80):
            raise ValueError("Reviewer required")
        if not isinstance(reason, str) or not (5 <= len(reason.strip()) <= 1000):
            raise ValueError("Explicit review reason required")
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("Run ID required")
        from .guard_audit import GuardAuditStore
        store = GuardAuditStore(self.path)
        # Use a single transaction for chain check, eligibility and review insertion.
        # Context-managed SQLite transactions do not close file handles on exit.
        # Explicit closing is essential for Windows ephemeral demo DB cleanup.
        with closing(store._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            if not store.verify_chain(conn=conn) or not self.verify_reviews(conn=conn):
                raise ValueError("Audit or review integrity invalid")
            row = conn.execute(
                "SELECT decision, event_id FROM guard_run_registry WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is None:
                raise ValueError("Decision not found")
            payload = json.loads(row[0])
            decision = payload["decision"]["decision"]
            if action == "AUTHORIZE_SIMULATION" and decision != "APPROVE":
                raise ValueError("Only eligible APPROVE decisions may authorize a simulation")
            conn.execute("""CREATE TABLE IF NOT EXISTS guard_human_reviews (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES guard_run_registry(run_id),
                decision_event_id INTEGER NOT NULL REFERENCES guard_audit_events(event_id),
                reviewer TEXT NOT NULL,
                action TEXT NOT NULL,
                reason TEXT NOT NULL,
                reviewed_at TEXT NOT NULL,
                record_hash TEXT NOT NULL
            )""")
            # The original decision is never overwritten. The review is an
            # additional explicit record, not a trade or a policy override.
            reviewed_at = datetime.now(timezone.utc).isoformat()
            digest = hashlib.sha256(json.dumps(
                [run_id, row[1], reviewer.strip(), action, reason.strip(), reviewed_at],
                ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")).hexdigest()
            cur = conn.execute(
                """INSERT INTO guard_human_reviews
                (run_id, decision_event_id, reviewer, action, reason, reviewed_at, record_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (run_id, row[1], reviewer.strip(), action, reason.strip(), reviewed_at, digest),
            )
            return {"review_id": cur.lastrowid, "action": action, "decision": decision,
                    "simulated_only": True, "trade_executed": False, "record_hash": digest}

    def verify_reviews(self, *, conn: sqlite3.Connection | None = None) -> bool:
        """Detect changes to stored review fields (not privileged history rewrites)."""
        from .guard_audit import GuardAuditStore
        store = GuardAuditStore(self.path)
        owned = conn is None
        if owned:
            conn = store._connect()
        try:
            if not store.verify_chain(conn=conn):
                return False
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='guard_human_reviews'"
            ).fetchone()
            if not exists:
                return True
            rows = conn.execute(
                """SELECT run_id, decision_event_id, reviewer, action, reason,
                          reviewed_at, record_hash FROM guard_human_reviews
                   ORDER BY review_id"""
            ).fetchall()
            for run_id, event_id, reviewer, action, reason, reviewed_at, recorded in rows:
                expected = hashlib.sha256(json.dumps(
                    [run_id, event_id, reviewer, action, reason, reviewed_at],
                    ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")).hexdigest()
                if recorded != expected:
                    return False
                decision_row = conn.execute(
                    "SELECT decision FROM guard_run_registry WHERE run_id=? AND event_id=?",
                    (run_id, event_id),
                ).fetchone()
                if decision_row is None:
                    return False
                try:
                    decision = json.loads(decision_row[0])["decision"]["decision"]
                except (ValueError, TypeError, KeyError):
                    return False
                if action not in ("ACKNOWLEDGE", "REQUEST_EXCEPTION", "AUTHORIZE_SIMULATION"):
                    return False
                if action == "AUTHORIZE_SIMULATION" and decision != "APPROVE":
                    return False
            return True
        finally:
            if owned:
                conn.close()
