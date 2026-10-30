"""Local SQLite append-only application audit for simulated Guard decisions.

Hashes are tamper-evident only; a privileged database editor can rewrite history.
No real order execution, no external IO other than the explicit SQLite file.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _digest(previous: str, payload: bytes) -> str:
    return hashlib.sha256(b"proofinvest.audit.v1\x00" + previous.encode("ascii") + b"\x00" + payload).hexdigest()


class GuardAuditStore:
    def __init__(self, path: str | Path):
        self.path = str(path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("""CREATE TABLE IF NOT EXISTS guard_audit_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(run_id, sequence)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS guard_run_registry (
            run_id TEXT PRIMARY KEY,
            request_hash TEXT NOT NULL,
            decision TEXT NOT NULL,
            event_id INTEGER NOT NULL REFERENCES guard_audit_events(event_id)
        )""")
        return conn

    def record_decision(self, run_id: str, request: Mapping[str, Any],
                        decision: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(run_id, str) or not (1 <= len(run_id) <= 128) or not all(
            c.isascii() and (c.isalnum() or c in "-_") for c in run_id
        ):
            raise ValueError("Invalid run id")
        if not isinstance(request, Mapping) or not isinstance(decision, Mapping):
            raise ValueError("Invalid payload")
        if decision.get("schema") != "proofinvest.guard-decision.v1" or decision.get("decision") not in (
            "APPROVE", "HOLD", "REJECT"
        ) or decision.get("trade_executed") is not False or decision.get("human_approved") is not False:
            raise ValueError("Only non-executing Guard decisions can be recorded")
        request_hash = hashlib.sha256(_canonical(dict(request))).hexdigest()
        event_payload = {"request_hash": request_hash, "decision": dict(decision)}
        payload_json = _canonical(event_payload).decode("utf-8")
        # A sqlite3.Connection context manager commits/rolls back but does NOT
        # close the handle. Close explicitly, including on exceptions, so
        # Windows can remove/rename temporary audit databases immediately.
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT request_hash, decision, event_id FROM guard_run_registry WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if existing:
                if existing[0] != request_hash or existing[1] != payload_json:
                    raise ValueError("Run ID reused with different inputs")
                row = conn.execute(
                    "SELECT event_hash FROM guard_audit_events WHERE event_id=?", (existing[2],)
                ).fetchone()
                if row is None or not self.verify_chain(conn=conn):
                    raise ValueError("Audit history invalid")
                return {"event_id": existing[2], "event_hash": row[0], "replayed": True}
            last = conn.execute(
                "SELECT event_hash FROM guard_audit_events ORDER BY event_id DESC LIMIT 1"
            ).fetchone()
            if not self.verify_chain(conn=conn):
                raise ValueError("Audit history invalid")
            previous = last[0] if last else "0" * 64
            digest = _digest(previous, payload_json.encode("utf-8"))
            now = datetime.now(timezone.utc).isoformat()
            cursor = conn.execute(
                """INSERT INTO guard_audit_events
                (run_id, sequence, event_type, payload_json, previous_hash, event_hash, created_at)
                VALUES (?, 1, 'GUARD_DECISION', ?, ?, ?, ?)""",
                (run_id, payload_json, previous, digest, now),
            )
            conn.execute(
                "INSERT INTO guard_run_registry (run_id, request_hash, decision, event_id) VALUES (?, ?, ?, ?)",
                (run_id, request_hash, payload_json, cursor.lastrowid),
            )
            return {"event_id": cursor.lastrowid, "event_hash": digest, "replayed": False}

    def verify_chain(self, *, conn: sqlite3.Connection | None = None) -> bool:
        owned = conn is None
        if owned:
            conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT event_id, run_id, sequence, event_type, payload_json, previous_hash, event_hash "
                "FROM guard_audit_events ORDER BY event_id"
            ).fetchall()
            previous = "0" * 64
            for event_id, run_id, seq, kind, payload, prev, digest in rows:
                # SQLite TEXT affinity does not stop a corrupted row from
                # containing BLOB values. Never crash an integrity check on
                # tampered local data: reject it before hashing or JSON parsing.
                if not all(isinstance(value, str) for value in
                           (run_id, kind, payload, prev, digest)):
                    return False
                if (len(prev) != 64 or len(digest) != 64 or
                        any(char not in "0123456789abcdef" for char in prev + digest)):
                    return False
                if seq != 1 or kind != "GUARD_DECISION" or prev != previous:
                    return False
                try:
                    matches = _digest(prev, payload.encode("utf-8")) == digest
                except (UnicodeError, ValueError):
                    return False
                if not matches:
                    return False
                registry = conn.execute(
                    "SELECT request_hash, decision, event_id FROM guard_run_registry WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if registry is None or registry[1] != payload or registry[2] != event_id:
                    return False
                try:
                    decoded = json.loads(payload)
                    if (decoded["request_hash"] != registry[0]
                            or decoded["decision"].get("schema") != "proofinvest.guard-decision.v1"
                            or decoded["decision"].get("decision") not in ("APPROVE", "HOLD", "REJECT")
                            or decoded["decision"].get("trade_executed") is not False
                            or decoded["decision"].get("human_approved") is not False):
                        return False
                except (AttributeError, KeyError, ValueError, TypeError):
                    return False
                previous = digest
            return conn.execute("SELECT COUNT(*) FROM guard_run_registry").fetchone()[0] == len(rows)
        finally:
            if owned:
                conn.close()
