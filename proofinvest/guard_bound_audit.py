"""Read back a specific Guard audit event and prove its evidence hash binding.

This adds a second, read-only verification after audit creation. SHA-256
chaining alone is not proof that the event belongs to the evidence/claim
currently displayed. The request hash must also match an independently
reconstructed offline risk, verdict, policy and evidence fingerprint.

This is still a LOCAL tamper-evidence check; privileged SQLite rewrites are
not cryptographically prevented without external anchoring.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from .guard_audit import GuardAuditStore, _canonical
from .guard_review import GuardReviewStore
from .guard_sec_adapter import evaluate_sec_guard

_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_RUN = re.compile(r"[A-Za-z0-9_-]{1,128}\Z", re.ASCII)


def verify_bound_guard_audit(
    database_path: str | Path,
    *,
    run_id: str,
    source_evidence_digest: str,
    financial_status: str,
    risk_evidence: Mapping[str, Any],
    event_id: int,
    event_hash: str,
    guard_decision: Mapping[str, Any],
    human_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify read-back of one persisted event against its precise source.

    No writes, creation, network, trade, source trust promotion or raw filing
    text. Returns allowlisted safety signals only or fails closed.
    """
    if (not isinstance(run_id, str) or _RUN.fullmatch(run_id) is None
            or not isinstance(source_evidence_digest, str)
            or _SHA.fullmatch(source_evidence_digest) is None
            or type(event_id) is not int or event_id <= 0
            or not isinstance(event_hash, str) or _SHA.fullmatch(event_hash) is None
            or financial_status not in ("calculated_unverified", "conflict")
            or not isinstance(risk_evidence, Mapping)
            or not isinstance(guard_decision, Mapping)
            or human_review is not None and not isinstance(human_review, Mapping)):
        raise ValueError("INVALID_BOUND_GUARD_AUDIT_INPUT")
    audit_file = Path(database_path).expanduser()
    if not audit_file.is_file() or audit_file.is_symlink():
        raise ValueError("BOUND_GUARD_AUDIT_FILE_NOT_FOUND")
    if (risk_evidence.get("risk_calculated") is not False
            or risk_evidence.get("source_authenticated") is not False
            or risk_evidence.get("financial_values_authenticated") is not False
            or risk_evidence.get("source_rights_verified") is not False
            or risk_evidence.get("status") not in ("reviewed_unverified", "unavailable")):
        raise ValueError("UNTRUSTED_RISK_AUDIT_INPUT")
    expected_mapped = evaluate_sec_guard(
        {"status": financial_status}, risk=risk_evidence
    )
    expected_guard = expected_mapped["guard"]
    if (expected_guard.get("decision") !=
            ("REJECT" if financial_status == "conflict" else "HOLD")
            or expected_guard != dict(guard_decision)
            or expected_guard.get("source_authenticated") is not False
            or expected_guard.get("human_approved") is not False
            or expected_guard.get("trade_executed") is not False):
        raise ValueError("GUARD_DECISION_DOES_NOT_MATCH_EVIDENCE")
    expected_request = {
        "sec_verdict": {"status": financial_status},
        "sec_status": expected_mapped["sec_status"],
        "source_authenticated": False,
        "risk": dict(risk_evidence),
        "policy_version": expected_guard["policy_version"],
        "source_evidence_digest": source_evidence_digest,
    }
    request_hash = hashlib.sha256(_canonical(expected_request)).hexdigest()
    expected_payload = _canonical({
        "request_hash": request_hash, "decision": expected_guard,
    }).decode("utf-8")
    # Read-only connection means this check cannot create or silently mutate
    # an audit database. BEGIN pins a consistent SQLite read snapshot.
    uri = audit_file.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=10)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        store = GuardAuditStore(audit_file)
        if (not store.verify_chain(conn=conn)
                or not GuardReviewStore(audit_file).verify_reviews(conn=conn)):
            raise ValueError("AUDIT_OR_REVIEW_CHAIN_INVALID")
        row = conn.execute(
            """SELECT r.request_hash, r.decision, r.event_id,
                      e.payload_json, e.event_hash
               FROM guard_run_registry AS r
               JOIN guard_audit_events AS e ON e.event_id = r.event_id
               WHERE r.run_id = ? AND e.run_id = ?""",
            (run_id, run_id),
        ).fetchone()
        if (row is None or row[0] != request_hash or row[1] != expected_payload
                or row[2] != event_id or row[3] != expected_payload
                or row[4] != event_hash):
            raise ValueError("STORED_GUARD_NOT_BOUND_TO_CURRENT_EVIDENCE")
        review_id: int | None = None
        if human_review is not None:
            review_id = human_review.get("review_id")
            if (type(review_id) is not int or review_id <= 0
                    or human_review.get("action") not in (
                        "ACKNOWLEDGE", "REQUEST_EXCEPTION",
                    )
                    or human_review.get("decision") != expected_guard["decision"]
                    or human_review.get("trade_executed") is not False
                    or human_review.get("simulated_only") is not True
                    or not isinstance(human_review.get("record_hash"), str)
                    or _SHA.fullmatch(human_review["record_hash"]) is None):
                raise ValueError("INVALID_BOUND_HUMAN_REVIEW")
            review_row = conn.execute(
                """SELECT run_id, decision_event_id, action, record_hash
                   FROM guard_human_reviews WHERE review_id = ?""",
                (review_id,),
            ).fetchone()
            if (review_row is None or review_row != (
                    run_id, event_id, human_review["action"],
                    human_review["record_hash"])):
                raise ValueError("HUMAN_REVIEW_DOES_NOT_MATCH_GUARD_EVENT")
    return {
        "schema": "proofinvest.guard-bound-evidence-readback.v1",
        "status": "verified_local_hash_binding_only",
        "run_id": run_id,
        "event_id": event_id,
        "event_hash": event_hash,
        "source_evidence_digest": source_evidence_digest,
        "guard_decision": expected_guard["decision"],
        "review_id": review_id,
        "verified_against_persisted_request": True,
        "audit_chain_valid": True,
        "human_review_chain_valid": True,
        "external_origin_authenticated": False,
        "externally_anchored": False,
        "trade_executed": False,
    }
