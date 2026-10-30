"""Read-only inspection of a CLOSED, locally supplied Guard SQLite snapshot.

Never extracts decision payloads, review text, keys, paths or private filings.
Does not create tables, write audit rows, or claim independent SEC origin.
This verifies application-level hashes only; a privileged editor can rewrite
both rows and hashes. WAL/SHM/journal sidecars are refused to prevent reviewing
an inconsistent live snapshot. Only inspect a quiescent, copied database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import stat
from pathlib import Path
from typing import Any

from .guard_audit import GuardAuditStore
from .guard_review import GuardReviewStore

MAX_DB_BYTES = 8_000_000
MAX_ROWS = 1000


def _closed_regular_file(location: str | Path) -> Path:
    if not isinstance(location, (str, Path)) or not str(location).strip():
        raise ValueError("INVALID_AUDIT_SNAPSHOT")
    target = Path(location).expanduser()
    if target.is_symlink() or not target.is_file():
        raise ValueError("INVALID_AUDIT_SNAPSHOT")
    actual = target.resolve(strict=True)
    info = actual.stat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_DB_BYTES:
        raise ValueError("INVALID_AUDIT_SNAPSHOT")
    # Never silently ignore possible uncheckpointed WAL history.
    for suffix in ("-wal", "-shm", "-journal"):
        if target.with_name(target.name + suffix).exists():
            raise ValueError("AUDIT_SNAPSHOT_NOT_CLOSED")
    return actual


def inspect_guard_snapshot(location: str | Path) -> dict[str, Any]:
    """Return a small, non-sensitive structural/integrity summary.

    Immutable SQLite URI is read-only and does not create WAL/SHM sidecars.
    Forensic use requires a frozen database copy; this API does not attest
    that the user's file was original or unmodified by privileged actors.
    """
    target = _closed_regular_file(location)
    # DB checksum is informational and not a signature; hash bounded source.
    h = hashlib.sha256()
    with target.open("rb") as f:
        while data := f.read(65536):
            h.update(data)
    byte_digest = h.hexdigest()
    try:
        con = sqlite3.connect(target.as_uri() + "?mode=ro&immutable=1",
                              uri=True, timeout=2)
        try:
            con.execute("PRAGMA query_only=ON")
            schema = {
                row[0] for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if not {"guard_audit_events", "guard_run_registry"} <= schema:
                raise ValueError("AUDIT_SNAPSHOT_SCHEMA_MISSING")
            events = con.execute(
                "SELECT COUNT(*) FROM guard_audit_events"
            ).fetchone()[0]
            registry = con.execute(
                "SELECT COUNT(*) FROM guard_run_registry"
            ).fetchone()[0]
            review_count = (
                con.execute("SELECT COUNT(*) FROM guard_human_reviews").fetchone()[0]
                if "guard_human_reviews" in schema else 0
            )
            if (not 1 <= events <= MAX_ROWS or registry != events
                    or not 0 <= review_count <= MAX_ROWS):
                raise ValueError("AUDIT_SNAPSHOT_BOUNDS")
            if (not GuardAuditStore(target).verify_chain(conn=con)
                    or not GuardReviewStore(target).verify_reviews(conn=con)):
                raise ValueError("AUDIT_SNAPSHOT_CHAIN_INVALID")
            # Never return raw request or review content. Safely tally
            # decisions from already verified payload records.
            counts = {"HOLD": 0, "REJECT": 0, "APPROVE": 0}
            for (record,) in con.execute("SELECT decision FROM guard_run_registry"):
                decision = json.loads(record)["decision"]["decision"]
                if decision not in counts:
                    raise ValueError("AUDIT_SNAPSHOT_DECISION_INVALID")
                counts[decision] += 1
            if sum(counts.values()) != events:
                raise ValueError("AUDIT_SNAPSHOT_COUNT_INVALID")
        finally:
            con.close()
    except (sqlite3.DatabaseError, sqlite3.OperationalError, KeyError,
            IndexError, TypeError, UnicodeError, RecursionError) as exc:
        raise ValueError("AUDIT_SNAPSHOT_INTEGRITY_UNAVAILABLE") from exc
    # Immutable read-only snapshots must remain byte-stable during inspection.
    check = hashlib.sha256()
    with target.open("rb") as f:
        while data := f.read(65536):
            check.update(data)
    if check.hexdigest() != byte_digest:
        raise ValueError("AUDIT_SNAPSHOT_CHANGED_DURING_READ")
    return {
        "schema": "proofinvest.guard-audit-snapshot-inspection.v1",
        "status": "LOCAL_HASH_CHAIN_VALID",
        "audit_events": events,
        "human_reviews": review_count,
        "decisions": counts,
        "database_sha256": byte_digest,
        "database_authenticated": False,
        "sec_issuer_authenticated": False,
        "investment_advice": False,
        "trade_executed": False,
        "official_contest_submission": False,
        "raw_record_content_exported": False,
        "trust_scope": "CLOSED_OFFLINE_SQLITE_APPLICATION_HASH_ONLY",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only local Guard SQLite hash-chain check; NO SEC/trade"
    )
    parser.add_argument("database", type=Path)
    args = parser.parse_args(argv)
    try:
        result = inspect_guard_snapshot(args.database)
    except (ValueError, OSError, RuntimeError):
        parser.exit(2, "Guard offline inspection blocked: integrity unavailable\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
